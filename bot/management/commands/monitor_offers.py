import asyncio
import logging
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Cache em memória para last_processed_id ─────────────────────────────────
# Evita chamadas constantes ao banco em contexto async — mais seguro e rápido.
# Na inicialização, carrega do banco (persiste entre deploys).
# A cada save, atualiza a memória E persiste no banco.
_last_id: int = 0
_last_id_loaded: bool = False


def load_last_id() -> int:
    """
    Retorna o último ID processado.
    Primeira chamada: lê do banco PostgreSQL (persiste entre deploys).
    Chamadas seguintes: usa cache em memória (rápido, sem issues de thread).
    """
    global _last_id, _last_id_loaded
    if _last_id_loaded:
        return _last_id
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        val = BotConfig.get('last_processed_id', '0')
        _last_id = int(val)
        logger.info(f"📌 Último ID carregado do banco: {_last_id}")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível carregar last_id do banco: {e}. Usando 0.")
        _last_id = 0
    _last_id_loaded = True
    return _last_id


def save_last_id(msg_id: int):
    """
    Salva o último ID processado na memória e no banco de dados.
    """
    global _last_id
    _last_id = msg_id  # Atualiza memória imediatamente
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        BotConfig.set('last_processed_id', msg_id)
    except Exception as e:
        logger.error(f"❌ Erro ao persistir last_id={msg_id} no banco: {e}")


class Command(BaseCommand):
    help = 'Monitor zFinnY -> Telegram + WhatsApp (Autônomo, PC pode estar desligado)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        group_id = int(getattr(settings, 'TELEGRAM_GROUP_ID', 0))

        async def main():
            client = TelegramClient('session_monitor', api_id, api_hash, connection_retries=None)
            await client.start()

            logger.info("🔍 Localizando ID do canal zFinnY...")
            target_id = None
            async for dialog in client.iter_dialogs():
                if "zFinnY" in dialog.name:
                    target_id = dialog.id
                    logger.info(f"✅ CANAL ENCONTRADO: {dialog.name} (ID: {target_id})")
                    break

            if not target_id:
                target_id = -1002216599534
                logger.warning(f"⚠️ Usando ID padrão: {target_id}")

            async def process_message(message):
                """Converte links e envia para Telegram + WhatsApp"""
                msg_text = message.message or ""

                if not msg_text and not message.photo:
                    return False

                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:60]}...")

                # ─── Converte links e processa texto ─────────────────────────
                from bot.services import convert_to_affiliate_link, send_whatsapp_message

                channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')

                modified_text = msg_text
                
                # 1. Substitui nomes de canais
                modified_text = re.sub(r'(?i)zFinnY|CaCau|André Indica|Tecnan', channel_name, modified_text)

                # 2. Remove o rodapé antigo do grupo (Limpeza Pesada)
                # Remove o emoji da sacola (várias versões) e qualquer linha residual
                modified_text = modified_text.replace('🛍️', '').replace('🛍', '')
                modified_text = re.sub(r'(?i)Grupo de promos.*?(?:\n|$)', '', modified_text)
                modified_text = re.sub(r'https?://t\.me/\S+', '', modified_text)
                # Remove linhas vazias excessivas que a sacola pode ter deixado
                modified_text = re.sub(r'\n\s*\n', '\n\n', modified_text)

                # 3. Converte links de produtos
                links = re.findall(r'(https?://\S+)', modified_text)
                converted_any = False
                for link in links:
                    is_telegram = 't.me/' in link
                    is_tecnan = 'tecnan.com.br' in link
                    is_awin = 'awin1.com' in link or 'tidd.ly' in link
                    is_amazon = 'amazon.com.br' in link or 'amzn.to' in link
                    is_shopee = 'shopee.com.br' in link or 's.shopee' in link
                    is_ml = 'mercadolivre' in link or 'meli.la' in link or 'mlstatic' in link
                    is_ali = 'aliexpress.com' in link or 's.click.ali' in link
                    is_kabum = 'kabum.com.br' in link
                    is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link

                    if is_telegram or is_tecnan:
                        modified_text = modified_text.replace(link, '') # Remove links de outros telegrams
                        continue

                    if is_awin:
                        converted_any = True
                        continue

                    if any([is_amazon, is_shopee, is_ml, is_ali, is_kabum, is_magalu]):
                        converted = convert_to_affiliate_link(link)
                        if converted:
                            modified_text = modified_text.replace(link, converted)
                            converted_any = True

                if not converted_any:
                    logger.info("ℹ️ Nenhum link convertível. Ignorando.")
                    return False

                # 4. Adiciona o novo rodapé do site
                modified_text = modified_text.strip()
                modified_text += "\n\n✨ Conheça mais sobre meu trabalho:\nwww.andreindica.com.br"

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
                    # asyncio.to_thread roda send_alerts em thread separada
                    # evitando SynchronousOnlyOperation do Django ORM em contexto async
                    await asyncio.to_thread(send_alerts, modified_text, photo_path)
                    logger.info("🔔 Alertas de usuários verificados/enviados")
                except Exception as alert_err:
                    logger.error(f"❌ Erro ao enviar alertas: {alert_err}")

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
                last_id = load_last_id()
                if msg.id <= last_id:
                    return
                success = await process_message(msg)
                if success:
                    save_last_id(msg.id)

            # ─── POLLING INTELIGENTE ──────────────────────────────────────────────
            async def smart_polling():
                while True:
                    try:
                        last_id = load_last_id()
                        messages = await client.get_messages(target_id, limit=10, min_id=last_id)
                        if messages:
                            for msg in reversed(list(messages)):
                                if msg.id > last_id:
                                    success = await process_message(msg)
                                    if success:
                                        save_last_id(msg.id)
                                        last_id = msg.id
                        await client.get_me()
                        logger.info("💓 Check-up automático em 1 canais realizado")
                    except Exception as e:
                        logger.error(f"Erro no polling: {e}")
                    await asyncio.sleep(30)

            # ─── CONVITE PERIÓDICO PARA O BOT DE ALERTAS ────────────────────
            INVITE_MSG = (
                "🔔 *Quer receber alertas personalizados de promoções?*\n\n"
                "Cadastre suas palavras-chave no nosso bot de alertas e seja "
                "notificado *no privado* sempre que uma promoção compatível "
                "aparecer aqui no grupo!\n\n"
                "✅ Totalmente *gratuito*\n"
                "✅ Você escolhe o que quer monitorar\n"
                "✅ Receba no seu Telegram instantaneamente\n\n"
                "👇 *Clique abaixo para ativar seus alertas:*\n"
                "➡️ https://t.me/andreindica_bot"
            )

            async def send_invite_periodically():
                # Aguarda 30s para o bot estabilizar antes do primeiro envio
                await asyncio.sleep(30)
                while True:
                    try:
                        await client.send_message(group_id, INVITE_MSG, parse_mode='md')
                        logger.info("📢 Mensagem de convite enviada ao grupo!")
                    except Exception as e:
                        logger.error(f"Erro ao enviar convite: {e}")
                    # Envia a cada 6 horas
                    await asyncio.sleep(6 * 60 * 60)

            logger.info("🚀 MONITOR AUTÔNOMO INICIADO! (Bot de Alertas Ativo)")
            await asyncio.gather(
                client.run_until_disconnected(),
                smart_polling(),
                send_invite_periodically()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado pelo usuário.')
        except Exception as e:
            logger.error(f"Erro Crítico: {e}")
