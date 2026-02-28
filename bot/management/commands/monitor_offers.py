import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor zFinnY -> André Bot (Versão Diagnóstico)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        bot_username = 'andreindica_bot' # Usando o username para garantir

        async def main():
            client = TelegramClient('session_monitor', api_id, api_hash)
            await client.start()
            
            logger.info("🚀 MONITOR INICIADO! Escutando todas as mensagens da conta...")

            # Handler universal: escuta TUDO e filtra por nome
            @client.on(events.NewMessage)
            @client.on(events.MessageEdited)
            async def universal_handler(event):
                try:
                    chat = await event.get_chat()
                    chat_name = getattr(chat, 'title', '') or getattr(chat, 'username', '') or ''
                    
                    # Se a mensagem vier do zFinnY
                    if "zFinnY" in chat_name:
                        msg_text = event.message.message or ""
                        logger.info(f"🔥 MENSAGEM CAPTURADA de '{chat_name}': {msg_text[:50]}...")
                        
                        # Encaminha para o André Bot
                        await client.forward_messages(bot_username, event.message)
                        logger.info(f"✅ Encaminhado para @{bot_username}")
                except Exception as e:
                    pass # Evita travar o monitor por erros bobos

            # Sinal de vida a cada 60 segundos nos logs
            async def heatbeat():
                while True:
                    logger.info("💓 Monitor está vivo e escutando...")
                    await asyncio.sleep(60)

            # Roda o heartbeat e o monitor juntos
            await asyncio.gather(
                client.run_until_disconnected(),
                heatbeat()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado.')
        except Exception as e:
            logger.error(f"Erro fatal no monitor: {e}")
