import asyncio
import logging
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from asgiref.sync import sync_to_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Cache em memória para last_processed_id ─────────────────────────────────
# Evita chamadas constantes ao banco em contexto async — mais seguro e rápido.
# Na inicialização, carrega do banco (persiste entre deploys).
# A cada save, atualiza a memória E persiste no banco.
_last_id: int = 0
_last_id_loaded: bool = False
_processing_ids: set = set()


@sync_to_async
def _db_get_last_id():
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    return BotConfig.get('last_processed_id', '0')

@sync_to_async
def _db_set_last_id(msg_id):
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    BotConfig.set('last_processed_id', msg_id)

async def load_last_id() -> int:
    global _last_id, _last_id_loaded
    if _last_id_loaded:
        return _last_id
    try:
        val = await _db_get_last_id()
        _last_id = int(val)
        logger.info(f"📌 Último ID carregado do banco: {_last_id}")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível carregar last_id do banco: {e}. Usando 0.")
        _last_id = 0
    _last_id_loaded = True
    return _last_id

async def save_last_id(msg_id: int):
    global _last_id
    _last_id = msg_id
    try:
        await _db_set_last_id(msg_id)
    except Exception as e:
        logger.error(f"❌ Erro ao persistir last_id={msg_id} no banco: {e}")





class Command(BaseCommand):
    help = 'Monitor do canal de promoções -> Telegram + WhatsApp (Autônomo, PC pode estar desligado)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        group_id = int(getattr(settings, 'TELEGRAM_GROUP_ID', 0))

        async def main():
            string_session = getattr(settings, 'TELEGRAM_STRING_SESSION', None)
            if string_session:
                logger.info("📡 Iniciando sessão via StringSession...")
                client = TelegramClient(StringSession(string_session), api_id, api_hash, connection_retries=None)
            else:
                logger.info("📂 Iniciando sessão via arquivo local...")
                client = TelegramClient('session_monitor', api_id, api_hash, connection_retries=None)
            
            await client.start()

            source_channel = getattr(settings, 'SOURCE_CHANNEL_USERNAME', 'zFinnY').strip()
            source_channel_norm = source_channel.casefold()

            logger.info(f"🔍 Localizando ID do canal {source_channel}...")
            target_id = None
            async for dialog in client.iter_dialogs():
                dialog_name = (dialog.name or '').casefold()
                dialog_username = (getattr(dialog, 'username', None) or '').casefold()
                if source_channel_norm in dialog_name or source_channel_norm == dialog_username:
                    target_id = dialog.id
                    logger.info(f"✅ CANAL ENCONTRADO: {dialog.name} (ID: {target_id})")
                    break

            if not target_id:
                logger.warning(f"⚠️ Canal não encontrado: {source_channel}. Verifique o valor de SOURCE_CHANNEL_USERNAME (pode ser o @username OU o nome exato do canal).")
                return

            # ─── COLD START: banco vazio, pular histórico ─────────────────────
            # Quando o banco está recém-criado/vazio, last_id parte de 0 e o
            # polling reprocessaria os últimos posts do canal (disparos duplicados).
            # Detectamos isso e avançamos o last_id até o post mais recente,
            # processando apenas ofertas NOVAS daqui em diante.
            current_last = await load_last_id()
            if current_last == 0:
                try:
                    latest_msgs = await client.get_messages(target_id, limit=1)
                    if latest_msgs:
                        newest = latest_msgs[0].id
                        await save_last_id(newest)
                        logger.info(f"🧊 Cold start detectado (banco vazio). Pulando histórico, last_id inicializado em {newest}. Só novas ofertas serão processadas.")
                    else:
                        logger.info("🧊 Cold start: canal sem mensagens, last_id permanece 0.")
                except Exception as cold_err:
                    logger.error(f"❌ Erro no cold start: {cold_err}")

            async def process_message(message):
                """Converte links e envia para Telegram + WhatsApp"""
                msg_text = message.message or ""

                if not msg_text and not message.photo:
                    return False

                # ─── Filtro: Ignora mensagens sem links (comentários/avisos) ───
                if not re.search(r'https?://\S+', msg_text):
                    logger.info(f"ℹ️ Mensagem ignorada (não contém links)")
                    return False

                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:60]}...")

                # ─── Deduplicação: já foi postada antes? ─────────────────────
                # Evita disparos repetidos quando o bot reinicia/redeploy e
                # reprocessa mensagens antigas do canal.
                from bot.services import promo_ja_postada
                try:
                    ja_postada = await asyncio.to_thread(promo_ja_postada, msg_text)
                    if ja_postada:
                        logger.info("⏭️ Oferta já postada anteriormente, ignorada.")
                        return True
                except Exception as dup_err:
                    logger.error(f"❌ Erro deduplicação: {dup_err}")

                # ─── Filtro de Palavras Proibidas (Blacklist) ────────────────
                blacklist = ['youtube', 'youtu.be', 'terabyte', 'terabyteshop']
                if any(word in msg_text.lower() for word in blacklist):
                    logger.info(f"🚫 Mensagem ignorada (palavra na blacklist encontrada)")
                    return False

                # ─── Converte links e processa texto ─────────────────────────
                from bot.services import convert_to_affiliate_link, send_whatsapp_message, strip_promo_footer

                channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')

                modified_text = msg_text
                
                # 1. Substitui nomes de canais
                modified_text = re.sub(r'(?i)zFinnY|Iskandar|CaCau|André Indica|Tecnan', channel_name, modified_text)

                # 2. Remove o rodapé antigo do grupo (Limpeza Pesada)
                # Remove o emoji da sacola (várias versões) e qualquer linha residual
                modified_text = modified_text.replace('🛍️', '').replace('🛍', '')
                modified_text = re.sub(r'(?i)Grupo de promos.*?(?:\n|$)', '', modified_text)
                modified_text = re.sub(r'https?://t\.me/\S+', '', modified_text)
                # Substitui links do Linktree pelo link personalizado
                modified_text = re.sub(r'https?://linktr\.ee/\S+', 'https://links.andreindica.com.br/', modified_text)
                modified_text = strip_promo_footer(modified_text)
                # Remove linhas vazias excessivas
                modified_text = re.sub(r'\n\s*\n', '\n\n', modified_text)

                # 3. Converte links de produtos
                links = re.findall(r'(https?://\S+)', modified_text)
                converted_any = False
                has_ali = False

                # Deduplicação: remove links repetidos mantendo a ordem
                seen_links = []
                unique_links = []
                for lnk in links:
                    # Normaliza para comparação (remove parâmetros de rastreio)
                    # Exceção: links Awin possuem o destino real nos parâmetros.
                    if 'awin1.com' in lnk or 'tidd.ly' in lnk:
                        lnk_norm = lnk
                    else:
                        lnk_norm = lnk.split('?')[0].rstrip('/')
                        
                    if lnk_norm not in seen_links:
                        seen_links.append(lnk_norm)
                        unique_links.append(lnk)
                    else:
                        # Remove duplicata do texto diretamente
                        modified_text = modified_text.replace(lnk, '', 1)
                # Remove linhas vazias geradas pela remoção das duplicatas
                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)

                for link in unique_links:
                    is_telegram = 't.me/' in link
                    is_tecnan = 'tecnan.com.br' in link
                    is_awin = 'awin1.com' in link or 'tidd.ly' in link
                    is_amazon = 'amazon.com.br' in link or 'amzn.to' in link or 'link.amazon' in link
                    is_shopee = 'shopee.com.br' in link or 's.shopee' in link
                    is_ml = 'mercadolivre' in link or 'meli.la' in link or 'mlstatic' in link
                    is_ali = 'aliexpress.com' in link or 's.click.ali' in link
                    is_kabum = 'kabum.com.br' in link
                    is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link

                    if is_telegram or is_tecnan:
                        modified_text = modified_text.replace(link, '') # Remove links de outros telegrams
                        continue

                    if is_awin:
                        # Extrai a URL real do produto e gera novo link com nosso ID
                        import urllib.parse as _urlparse
                        from bot.services import convert_awin_link
                        extracted_url = None
                        if 'ued=' in link:
                            try:
                                ued_value = link.split('ued=')[1].split('&')[0]
                                extracted_url = _urlparse.unquote(ued_value)
                            except:
                                pass
                        if extracted_url:
                            new_awin = convert_awin_link(extracted_url)
                            if new_awin:
                                modified_text = modified_text.replace(link, new_awin)
                                converted_any = True
                                continue
                        converted_any = True
                        continue

                    if any([is_amazon, is_shopee, is_ml, is_ali, is_kabum, is_magalu]):
                        converted = convert_to_affiliate_link(link)
                        if converted:
                            if is_ali:
                                # O canal fonte já fornece links separados para App e PC com labels prontas.
                                # Apenas converte cada URL para o link de afiliado e substitui no lugar.
                                has_ali = True
                            
                            modified_text = modified_text.replace(link, converted)
                            # Remove linhas vazias extras
                            modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                            converted_any = True

                # Se não encontrar links de lojas (Amazon, AliExpress, etc.), ignoramos a mensagem.
                if not converted_any:
                    logger.info("🚫 Mensagem ignorada (nenhum link de loja detectado).")
                    return False

                # 4. Adiciona o novo rodapé do site
                # Remove seções PELO PC residuais e outras linhas de rodapé do canal fonte
                modified_text = re.sub(r'(?i)\n?⬇️?\s*PELO PC\s*\n?', '', modified_text)
                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                modified_text = modified_text.strip()

                if modified_text:
                    if has_ali:
                        modified_text += (
                            "\n\n💡 Dica: Comprando pelo aplicativo o desconto pode ser maior por causa das moedas.\n"
                            "Após clicar no link acima, você será direcionado para a página de moedas. Clique no primeiro anúncio.\n"
                            "Se o produto não aparecer, clique em 'DO BRASIL'."
                        )


                # ─── Baixa foto ──────────────────────────────────────────────
                photo_path = None
                if message.photo:
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    os.makedirs(temp_dir, exist_ok=True)
                    photo_path = await message.download_media(file=temp_dir)
                    if photo_path:
                        photo_path = os.path.abspath(photo_path)
                        logger.info(f"📸 Foto baixada: {photo_path}")

                # ─── Envia para o Telegram ───────────────────────────────────
                try:
                    if photo_path and os.path.exists(photo_path):
                        await client.send_file(group_id, photo_path, caption=modified_text[:1024])
                        logger.info("✅ Enviado para Telegram (com foto)")
                    else:
                        await client.send_message(group_id, modified_text)
                        logger.info("✅ Enviado para Telegram (só texto)")
                except Exception as tg_err:
                    logger.error(f"❌ Erro Telegram: {tg_err}")

                # ─── Envia para o WhatsApp ───────────────────────────────────
                try:
                    send_whatsapp_message(modified_text, photo_path)
                    logger.info("✅ Enviado para WhatsApp")
                except Exception as wa_err:
                    logger.error(f"❌ Erro WhatsApp: {wa_err}")

                # ─── Dispara alertas para usuários do Bot ────────────────────
                try:
                    from bot.alert_sender import send_alerts
                    await asyncio.to_thread(send_alerts, modified_text, photo_path)
                    logger.info("🔔 Alertas de usuários verificados/enviados")
                except Exception as alert_err:
                    logger.error(f"❌ Erro ao enviar alertas: {alert_err}")

                # ─── Salva a promo no banco para a página web ─────────────────
                try:
                    from bot.services import save_promo_to_db, _normalizar_url, _primeiro_link_produto
                    # Chave estável baseada no link BRUTO (msg_text), não no convertido.
                    chave_estavel = _normalizar_url(_primeiro_link_produto(msg_text))
                    await asyncio.to_thread(save_promo_to_db, modified_text, photo_path, source_channel, chave_estavel)
                    logger.info("💾 Promo salva no banco de dados")
                except Exception as db_err:
                    logger.error(f"❌ Erro ao salvar promo no banco: {db_err}")

                # ─── Publica Story no Instagram ─────────────────────────────
                try:
                    from bot.instagram_stories import post_instagram_story
                    await asyncio.to_thread(post_instagram_story, modified_text, photo_path)
                except Exception as ig_err:
                    logger.error(f"❌ Erro Instagram: {ig_err}")

                # ─── Limpa foto após 90s ─────────────────────────────────────
                if photo_path:
                    async def cleanup(path):
                        await asyncio.sleep(90)
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception:
                            pass
                    asyncio.create_task(cleanup(photo_path))

                return True

            # ─── LISTENER (Tempo Real) ───────────────────────────────────────
            @client.on(events.NewMessage(chats=target_id))
            async def handler(event):
                msg = event.message
                last_id = await load_last_id()
                if msg.id <= last_id or msg.id in _processing_ids:
                    return
                
                _processing_ids.add(msg.id)
                try:
                    await process_message(msg)
                    # Avança o last_id SEMPRE (mesmo ignorada) para não
                    # reprocessar mensagens antigas após restart/redeploy.
                    await save_last_id(msg.id)
                finally:
                    if msg.id in _processing_ids:
                        _processing_ids.remove(msg.id)

            # ─── POLLING INTELIGENTE ──────────────────────────────────────────────
            async def smart_polling():
                while True:
                    try:
                        last_id = await load_last_id()
                        messages = await client.get_messages(target_id, limit=10, min_id=last_id)
                        if messages:
                            for msg in reversed(list(messages)):
                                if msg.id > last_id and msg.id not in _processing_ids:
                                    _processing_ids.add(msg.id)
                                    try:
                                        await process_message(msg)
                                    finally:
                                        if msg.id in _processing_ids:
                                            _processing_ids.remove(msg.id)
                                        # Avança o last_id mesmo se ignorada/duplicada
                                        if msg.id > last_id:
                                            await save_last_id(msg.id)
                                            last_id = msg.id
                        await client.get_me()
                        logger.info("💓 Check-up automático realizado")
                    except Exception as e:
                        logger.error(f"Erro no polling: {e}")
                    await asyncio.sleep(30)

            logger.info("🚀 MONITOR AUTÔNOMO INICIADO! (Bot de Alertas Ativo)")
            await asyncio.gather(
                client.run_until_disconnected(),
                smart_polling()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado pelo usuário.')
        except Exception as e:
            logger.error(f"Erro Crítico: {e}")
