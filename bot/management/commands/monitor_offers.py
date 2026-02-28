import asyncio
import os
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events
from telegram.ext import ApplicationBuilder
from bot.services import process_offer_to_group

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitora um canal do Telegram e encaminha ofertas convertidas automaticamente'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        source_channel = getattr(settings, 'SOURCE_CHANNEL_USERNAME', 'zFinnY')
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

        if not api_id or not api_hash:
            self.stdout.write(self.style.ERROR('Erro: TELEGRAM_API_ID e TELEGRAM_API_HASH devem estar no .env'))
            return

        if not bot_token:
            self.stdout.write(self.style.ERROR('Erro: TELEGRAM_BOT_TOKEN não configurado'))
            return

        self.stdout.write(self.style.SUCCESS(f'Iniciando monitoramento do canal: {source_channel}'))

        async def main():
            # 1. Inicializa o Bot apenas para envio (sem polling para evitar conflito)
            from telegram import Bot
            bot_client = Bot(token=bot_token)

            # 2. Inicializa o UserBot (Telethon)
            # O arquivo 'session_monitor' salvará sua sessão para não precisar logar sempre
            client = TelegramClient('session_monitor', api_id, api_hash)

            @client.on(events.NewMessage(chats=source_channel))
            @client.on(events.MessageEdited(chats=source_channel))
            async def my_event_handler(event):
                try:
                    text = event.message.text
                    photo = None
                    
                    if not text:
                        # Se não tiver texto, pode ser uma mensagem apenas com mídia que foi editada
                        logger.info("Mensagem sem texto detectada, ignorando...")
                        return

                    logger.info(f"Conteúdo detectado em {source_channel}: {text[:50]}...")
                    
                    if event.message.photo:
                        # Baixa a foto na memória para enviar via bot
                        photo = await event.message.download_media(file=bytes)
                    
                    # Processa e envia para o grupo usando a lógica do bot
                    success = await process_offer_to_group(bot_client, text, photo)
                    
                    if success:
                        logger.info("✅ Oferta processada e encaminhada com sucesso.")
                    else:
                        logger.info("ℹ️ Mensagem ignorada (sem links de ofertas ou já processada).")
                        
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {e}")

            await client.start()
            self.stdout.write(self.style.SUCCESS('UserBot conectado! Aguardando novas postagens...'))
            await client.run_until_disconnected()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Monitoramento interrompido.'))
