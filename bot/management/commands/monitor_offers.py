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


def _save_promo_db(texto: str, photo_path: str = None):
    """
    Salva a promoção no banco de dados para exibição na página web.
    Detecta categoria automaticamente pelo conteúdo do texto.
    """
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import Promo

    # Detecta categoria pelo texto (Ordem de prioridade importa!)
    texto_lower = texto.lower()
    categoria = 'outros'
    
    # 1. Produtos Completos
    if any(k in texto_lower for k in ['notebook', 'laptop', 'macbook']):
        categoria = 'notebook'
    elif any(k in texto_lower for k in ['smartphone', 'celular', 'iphone', 'galaxy', 'moto g', 'poco', 'redmi']):
        categoria = 'celular'
    elif any(k in texto_lower for k in ['televisão', 'televisao', 'tv ', 'smart tv', 'polegada']):
        categoria = 'tv'
        
    # 2. Peças Principais
    elif any(k in texto_lower for k in ['placa de vídeo', 'placa de video', 'rtx', 'gtx', 'rx ', 'radeon', 'geforce']):
        categoria = 'placa_video'
    elif any(k in texto_lower for k in ['placa-mãe', 'placa mae', 'placa-mae', 'motherboard', ' b450 ', ' b550 ', ' a520 ', ' h610 ', ' b660 ', ' x670 ', ' am4 ', ' lga ']):
        categoria = 'placa_mae'
    elif any(k in texto_lower for k in ['processador', 'ryzen', 'intel core', 'amd core', ' i3 ', ' i5 ', ' i7 ', ' i9 ']):
        categoria = 'processador'
        
    # 3. Monitor e Periféricos
    elif any(k in texto_lower for k in ['monitor', 'display', 'ips ', 'oled', 'hz ', 'curvo']):
        categoria = 'monitor'
    elif any(k in texto_lower for k in ['headset', 'headphone', 'fone', 'airpods', 'buds', 'tws']):
        categoria = 'headset'
    elif any(k in texto_lower for k in ['teclado']):
        categoria = 'teclado'
    elif any(k in texto_lower for k in ['mouse']):
        categoria = 'mouse'
        
    # 4. Componentes Internos
    elif any(k in texto_lower for k in ['memória ram', 'memoria ram', 'ddr4', 'ddr5', ' dimm ']):
        categoria = 'memoria_ram'
    elif any(k in texto_lower for k in ['ssd', 'nvme', 'm.2', 'hd ', 'armazenamento', 'sata']):
        categoria = 'ssd'
        
    # 5. Outros
    elif any(k in texto_lower for k in ['cadeira', 'gamer chair']):
        categoria = 'cadeira'
    elif any(k in texto_lower for k in ['impressora']):
        categoria = 'impressora'

    import re
    import json

    # Extrai múltiplos links e seus respectivos contextos
    links_encontrados = []
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]
    
    for linha in linhas:
        # Encontra urls na linha
        urls_na_linha = re.findall(r'(https?://\S+)', linha)
        for url in urls_na_linha:
            if any(d in url for d in ['amazon', 'shopee', 'mercadolivre', 'kabum', 'magaz', 'awin', 'tidd']):
                url_limpa = url.rstrip(')')
                # Tenta achar um contexto (nome) antes da URL na mesma linha
                contexto = linha.replace(url, '').strip()
                # Limpa setinhas e emojis básicos residuais no final da frase
                contexto_limpo = re.sub(r'[:➡👉\-\s]+$', '', contexto).strip()
                
                # Se ainda tiver muito lixo de emoji no começo, também podemos limpar (ou deixar)
                nome_botao = contexto_limpo if contexto_limpo else "Ver Oferta"
                
                # Previne duplicatas exatas
                if not any(l['url'] == url_limpa for l in links_encontrados):
                    links_encontrados.append({
                        "nome": nome_botao,
                        "url": url_limpa
                    })

    # Pega pelo menos o primeiro link (mesmo sem loja reconhecida) se tiver, caso passe vazio nas regras
    if not links_encontrados:
        todas_urls = re.findall(r'(https?://\S+)', texto)
        if todas_urls:
            links_encontrados.append({
                "nome": "Ver Oferta",
                "url": todas_urls[0].rstrip(')')
            })

    if not links_encontrados:
        return  # Sem link não salva
    
    # Salva os links como um array JSON
    link_afiliado = json.dumps(links_encontrados, ensure_ascii=False)

    # Extrai título (primeira linha não vazia sem emojis/símbolos)
    titulo = ''
    for linha in texto.split('\n'):
        limpa = re.sub(r'[^\w\s.,!?-]', '', linha).strip()
        if len(limpa) > 10:
            titulo = limpa[:250]
            break

    # Extrai preço
    preco_match = re.search(r'R\$\s*[\d.,]+', texto)
    preco = preco_match.group(0).strip() if preco_match else ''

    # Extrai múltiplos cupons
    import json
    cupons_encontrados = []
    
    ignore_words = {'MERCADO', 'LIVRE', 'SHOPEE', 'AMAZON', 'KABUM', 'MAGAZINE', 'ALIEXPRESS', 'DESCONTO', 'NOVO', 'PRIME', 'NINJA', 'OFERTA', 'PROMO', 'CUPOM'}
    
    def is_valid_coupon(code):
        if not code or code.isnumeric() or len(code) < 4:
            return False
        if code.upper() in ignore_words:
            return False
        return True

    # 1. Busca padrão "R$XX OFF ... - CODIGO" ou "% OFF ... - CODIGO"
    matches_desc = re.finditer(r'(?i)(.*?(?:OFF|desconto).*?)-\s*([A-Z0-9]{4,20})(?=\s|$)', texto)
    for m in matches_desc:
        regra = m.group(1).strip()
        codigo = m.group(2).strip()
        if is_valid_coupon(codigo):
            cupons_encontrados.append({"regra": regra, "codigo": codigo})
            
    # 2. Varredura Inteligente Linha a Linha (com contexto anterior)
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]
    for i, linha in enumerate(linhas):
        codigo_encontrado = None
        regra_contexto = []
        
        # Tenta achar cupom no formato "Cupom: CODIGO" ou com "-"
        match_direto = re.search(r'(?i)cupom[:\s]+([A-Z0-9]{4,20})', linha)
        if match_direto:
            codigo_encontrado = match_direto.group(1).strip()
        elif '-' in linha and 'http' not in linha:
            parts = linha.rsplit('-', 1)
            codigo_potencial = parts[1].strip()
            if re.match(r'^[A-Z0-9]{4,20}$', codigo_potencial):
                codigo_encontrado = codigo_potencial
                if parts[0].strip():
                    regra_contexto.append(parts[0].strip())

        if codigo_encontrado and is_valid_coupon(codigo_encontrado):
            if not any(c['codigo'] == codigo_encontrado for c in cupons_encontrados):
                # Olha para as 2 linhas de cima buscando regras (OFF, limite, acima de)
                for lookback in range(1, 3):
                    if i - lookback >= 0:
                        l_ant = linhas[i - lookback]
                        if any(k in l_ant.lower() for k in ['off', 'limite', 'acima de', 'mínima', 'valor']):
                            # Remove emojis do começo se quiser, mas vamos pegar a linha
                            regra_limpa = re.sub(r'^[^\w\s]+', '', l_ant).strip()
                            if regra_limpa and regra_limpa not in regra_contexto:
                                regra_contexto.insert(0, regra_limpa)

                # Monta a regra final
                if regra_contexto:
                    regra_final = " | ".join(regra_contexto)
                else:
                    regra_final = "Cupom de Desconto"

                cupons_encontrados.append({"regra": regra_final, "codigo": codigo_encontrado})

    cupom_str = json.dumps(cupons_encontrados, ensure_ascii=False) if cupons_encontrados else ''

    # Processa imagem para a Web
    imagem_url = ''
    if photo_path and os.path.exists(photo_path):
        try:
            import shutil
            from django.conf import settings
            
            # Garante que a pasta media/promos existe
            media_promos_dir = os.path.join(settings.MEDIA_ROOT, 'promos')
            os.makedirs(media_promos_dir, exist_ok=True)
            
            # Gera nome do arquivo único baseado na data/hora
            import time
            filename = f"promo_{int(time.time())}_{os.path.basename(photo_path)}"
            new_path = os.path.join(media_promos_dir, filename)
            
            # Copia o arquivo para a pasta pública
            shutil.copy2(photo_path, new_path)
            
            # Salva a URL relativa
            imagem_url = f"{settings.MEDIA_URL}promos/{filename}"
        except Exception as img_err:
            logger.error(f"❌ Erro ao processar imagem para DB: {img_err}")

    # ===== SALVA NO BANCO DE DADOS =====
    try:
        from bot.models import Promo
        Promo.objects.create(
            titulo=titulo,
            preco=preco,
            cupom=cupom_str,  # <-- JSON string
            link_afiliado=link_afiliado,
            imagem_url=imagem_url,
            categoria=categoria,
            texto_original=texto[:2000]
        )
        logger.info(f"💾 Promoção salva no Banco de Dados (Web): {titulo[:30]}")
    except Exception as db_err:
        logger.error(f"❌ Erro ao salvar Promo no Banco de Dados: {db_err}")


class Command(BaseCommand):
    help = 'Monitor zFinnY -> Telegram + WhatsApp (Autônomo, PC pode estar desligado)'

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

                    if any([is_amazon, is_shopee, is_ml, is_ali, is_kabum, is_magalu, is_awin]):
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
                modified_text += "\n\n👇 *Clique abaixo para ativar seus alertas:*\n➡ https://t.me/alertas_andre_bot"

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
                    await asyncio.to_thread(_save_promo_db, modified_text, photo_path)
                    logger.info("💾 Promo salva no banco de dados")
                except Exception as db_err:
                    logger.error(f"❌ Erro ao salvar promo no banco: {db_err}")

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
                if msg.id <= last_id:
                    return
                success = await process_message(msg)
                if success:
                    await save_last_id(msg.id)

            # ─── POLLING INTELIGENTE ──────────────────────────────────────────────
            async def smart_polling():
                while True:
                    try:
                        last_id = await load_last_id()
                        messages = await client.get_messages(target_id, limit=10, min_id=last_id)
                        if messages:
                            for msg in reversed(list(messages)):
                                if msg.id > last_id:
                                    success = await process_message(msg)
                                    if success:
                                        await save_last_id(msg.id)
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
