import asyncio
import logging
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor zFinnY -> Telegram + WhatsApp (Modo Autônomo)'

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

            processed_ids = set()

            async def process_message(message):
                msg_id = message.id
                if msg_id in processed_ids:
                    return False

                processed_ids.add(msg_id)
                if len(processed_ids) > 500:
                    processed_ids.clear()
                    processed_ids.add(msg_id)

                msg_text = message.message or ""

                if not msg_text and not message.photo:
                    return False

                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:60]}...")

                # ─── Converte os links e processa texto ───────────────────────
                from bot.services import convert_to_affiliate_link, send_whatsapp_message

                personal_link = getattr(settings, 'PERSONAL_CHANNEL_LINK', '')
                channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')

                modified_text = msg_text
                # Substitui nomes de canais de terceiros pelo seu nome
                modified_text = re.sub(r'(?i)zFinnY|CaCau|André Indica|Tecnan', channel_name, modified_text)

                # Converte links
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
                    is_kabum = 'kabum.com.br' in link or 'tidd.ly' in link
                    is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link

                    if is_telegram or is_tecnan:
                        if personal_link and personal_link not in link:
                            modified_text = modified_text.replace(link, personal_link)
                        converted_any = True
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

                # ─── Baixa foto do Telegram ───────────────────────────────────
                photo_path = None
                if message.photo:
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    os.makedirs(temp_dir, exist_ok=True)
                    photo_path = await message.download_media(file=temp_dir)
                    if photo_path:
                        photo_path = os.path.abspath(photo_path)
                        logger.info(f"📸 Foto baixada: {photo_path}")

                # ─── Envia para o Telegram (Telethon) ────────────────────────
                try:
                    if not group_id:
                        raise ValueError("TELEGRAM_GROUP_ID não configurado")

                    if photo_path and os.path.exists(photo_path):
                        await client.send_file(
                            group_id,
                            photo_path,
                            caption=modified_text[:1024]
                        )
                        logger.info("✅ Enviado para Telegram (com foto)")
                    else:
                        await client.send_message(group_id, modified_text)
                        logger.info("✅ Enviado para Telegram (só texto)")
                except Exception as tg_err:
                    logger.error(f"❌ Erro ao enviar para Telegram: {tg_err}")

                # ─── Envia para o WhatsApp ───────────────────────────────────
                try:
                    send_whatsapp_message(modified_text, photo_path)
                    logger.info("✅ Enviado para WhatsApp")
                except Exception as wa_err:
                    logger.error(f"❌ Erro ao enviar para WhatsApp: {wa_err}")

                # ─── Limpa a foto do disco após 90s ─────────────────────────
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

            # Listener instantâneo
            @client.on(events.NewMessage(chats=target_id))
            @client.on(events.MessageEdited(chats=target_id))
            async def handler(event):
                await process_message(event.message)

            # Polling de fallback a cada 30s
            async def manual_polling():
                while True:
                    try:
                        messages = await client.get_messages(target_id, limit=3)
                        for msg in reversed(messages):
                            await process_message(msg)
                        await client.get_me()
                        logger.info("💓 Check-up automático em 1 canais realizado")
                    except Exception as e:
                        logger.error(f"Erro no polling: {e}")
                    await asyncio.sleep(30)

            logger.info("🚀 MONITOR AUTÔNOMO INICIADO!")
            await asyncio.gather(
                client.run_until_disconnected(),
                manual_polling()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado pelo usuário.')
        except Exception as e:
            logger.error(f"Erro Crítico: {e}")
