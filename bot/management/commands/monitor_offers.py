import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

# Configuração de Logs detalhada
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor Oficial zFinnY -> André Bot'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        bot_id = 8549195241 # ID do @andreindica_bot

        async def main():
            client = TelegramClient('session_monitor', api_id, api_hash)
            await client.start()
            
            # ID exato capturado do seu log anterior
            target_chat_id = -1002216599534 
            
            logger.info(f"🚀 MONITOR ATIVO para o canal ID: {target_chat_id} (zFinnY Promos)")

            # Captura Mensagens Novas E Mensagens Editadas
            @client.on(events.NewMessage(chats=target_chat_id))
            @client.on(events.MessageEdited(chats=target_chat_id))
            async def fast_forwarder(event):
                # Pegamos o texto da mensagem (ou a legenda da foto)
                msg_text = event.message.message or ""
                
                logger.info(f"🔔 Evento detectado! Texto: {msg_text[:100]}...")
                
                if not msg_text and not event.message.media:
                    logger.info("Mídia vazia ou sem texto, ignorando...")
                    return

                try:
                    # Encaminha o post ORIGINAL (com foto e tudo) para o André Bot
                    await client.forward_messages(bot_id, event.message)
                    logger.info(f"✅ Postagem encaminhada para o @andreindica_bot")
                except Exception as e:
                    logger.error(f"❌ Falha ao encaminhar: {e}")

            logger.info("📡 Aguardando a próxima oferta do zFinnY...")
            await client.run_until_disconnected()

        asyncio.run(main())
