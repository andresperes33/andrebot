import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitora o zFinnY Promos e encaminha para o André Bot'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        
        # ID do seu bot (@andreindica_bot)
        bot_id = 8549195241

        if not api_id or not api_hash:
            logger.error('Erro: TELEGRAM_API_ID e TELEGRAM_API_HASH devem estar no .env')
            return

        async def main():
            client = TelegramClient('session_monitor', api_id, api_hash)
            await client.start()
            
            logger.info("UserBot conectado. Procurando canal 'zFinnY Promos'...")
            
            # Procura o canal correto nos seus chats para não errar o ID
            target_chat = None
            async for dialog in client.iter_dialogs():
                if "zFinnY" in dialog.name:
                    target_chat = dialog.id
                    logger.info(f"✅ Canal encontrado: {dialog.name} (ID: {dialog.id})")
                    break
            
            if not target_chat:
                logger.warning("⚠️ Canal 'zFinnY' não encontrado na sua lista de chats. Tentando pelo username padrão...")
                target_chat = 'zFinnY'

            # Handler para mensagens e edições
            @client.on(events.NewMessage(chats=target_chat))
            @client.on(events.MessageEdited(chats=target_chat))
            async def forward_handler(event):
                try:
                    # Log para debug
                    text_preview = (event.message.text[:50] + "...") if event.message.text else "Mídia/Foto"
                    logger.info(f"Capturado do zFinnY: {text_preview}")
                    
                    # Encaminha para o André Bot
                    await client.forward_messages(bot_id, event.message)
                    logger.info("🚀 Encaminhado para o André Bot com sucesso!")
                except Exception as e:
                    logger.error(f"Erro ao encaminhar: {e}")

            logger.info("✅ Monitoramento ativo e aguardando postagens...")
            await client.run_until_disconnected()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado.')
