import asyncio
import logging
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor zFinnY -> Telegram + WhatsApp (Modo Autônomo)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)

        async def main():
            # Inicia o cliente Telethon (UserBot)
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
                logger.warning(f"⚠️ 'zFinnY' não achado na lista. Usando ID padrão: {target_id}")

            # Cache para evitar duplicados
            processed_ids = set()

            async def process_message(message):
                """Processa a mensagem: baixa foto e envia para Telegram + WhatsApp"""
                msg_id = message.id
                if msg_id in processed_ids:
                    return False

                # Marca como processado
                processed_ids.add(msg_id)
                if len(processed_ids) > 500:
                    processed_ids.clear()
                    processed_ids.add(msg_id)

                # Texto real da mensagem (Telethon usa .message, não .text)
                msg_text = message.message or ""

                # Se não tiver nem texto nem foto, ignora
                if not msg_text and not message.photo:
                    return False

                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:60]}...")

                # Baixa a foto localmente se existir
                photo_path = None
                if message.photo:
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    photo_path = await message.download_media(file=temp_dir)
                    if photo_path:
                        photo_path = os.path.abspath(photo_path)
                        logger.info(f"📸 Foto baixada: {photo_path}")

                # Envia para Telegram + WhatsApp
                from bot.services import process_offer_to_group
                await process_offer_to_group(client, msg_text, photo_path)
                logger.info("✅ Processado e enviado!")

                # Apaga a foto após 90 segundos para não encher o disco
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

            # LISTENER (Instantâneo - recebe push do Telegram)
            @client.on(events.NewMessage(chats=target_id))
            @client.on(events.MessageEdited(chats=target_id))
            async def handler(event):
                await process_message(event.message)

            # POLLING (Fallback a cada 30s para não perder mensagens)
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
