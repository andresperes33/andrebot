import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitora o zFinnY e apenas encaminha para o André Bot'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        source_channel = getattr(settings, 'SOURCE_CHANNEL_USERNAME', 'zFinnY')
        
        # ID fixo do seu bot (André Bot) extraído dos seus logs
        bot_id = 8549195241

        if not api_id or not api_hash:
            self.stdout.write(self.style.ERROR('Erro: chaves de API faltando no .env'))
            return

        async def main():
            # Inicializa apenas o UserBot (Sua conta)
            client = TelegramClient('session_monitor', api_id, api_hash)

            # Escuta novas mensagens e edições (para capturar o texto que vem depois da foto)
            @client.on(events.NewMessage(chats=source_channel))
            @client.on(events.MessageEdited(chats=source_channel))
            async def forward_handler(event):
                try:
                    # Apenas encaminha a mensagem original para o André Bot
                    logger.info(f"Encaminhando postagem de {source_channel} para o André Bot...")
                    await client.forward_messages(bot_id, event.message)
                    logger.info("✅ Encaminhado com sucesso!")
                except Exception as e:
                    logger.error(f"Erro ao encaminhar: {e}")

            await client.start()
            self.stdout.write(self.style.SUCCESS('Monitor de Encaminhamento Ativo!'))
            await client.run_until_disconnected()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Encaminhador parado.'))
