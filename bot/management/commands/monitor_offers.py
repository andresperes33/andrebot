import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor zFinnY -> André Bot (Modo Autônomo Independente)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        bot_username = 'andreindica_bot'

        async def main():
            # Inicia o cliente
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
                """Função central para processar e encaminhar se for novo"""
                msg_id = message.id
                if msg_id in processed_ids:
                    return False
                
                # Marca como processado
                processed_ids.add(msg_id)
                if len(processed_ids) > 500:
                    processed_ids.clear()
                    processed_ids.add(msg_id)

                # Se tiver foto, baixa ela
                photo_path = None
                if message.photo:
                    import os
                    # Salva temporariamente em uma pasta acessível
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    photo_path = await message.download_media(file=temp_dir)
                    if photo_path:
                        photo_path = os.path.abspath(photo_path)
                
                # Chama o serviço de processamento original do seu bot
                from bot.services import process_offer_to_group
                await process_offer_to_group(client, message.text, photo_path)
                
                # Tenta limpar a foto após um tempo para não encher o disco
                if photo_path and os.path.exists(photo_path):
                    try:
                        # Aguarda um pouco para dar tempo do envio terminar antes de apagar
                        await asyncio.sleep(60) 
                        os.remove(photo_path)
                    except:
                        pass
                
                msg_text = message.message or "Mídia"
                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:40]}...")
                
                # Encaminha para o André Bot
                await client.forward_messages(bot_username, message)
                logger.info("✅ Encaminhado com sucesso!")
                return True

            # 1. LISTENER (Instantâneo quando o Telegram manda o 'push')
            @client.on(events.NewMessage(chats=target_id))
            @client.on(events.MessageEdited(chats=target_id))
            async def handler(event):
                await process_message(event.message)

            # 2. POLLING (Fallback Manual - Funciona mesmo com Telegram do PC desligado)
            # Ele checa as últimas 3 mensagens a cada 30 segundos
            async def manual_polling():
                while True:
                    try:
                        # Pede as últimas mensagens manualmente pro servidor
                        messages = await client.get_messages(target_id, limit=3)
                        for msg in reversed(messages): # Pega da mais antiga pra mais nova
                            await process_message(msg)
                        
                        # "Cutuca" o servidor para manter a conexão ativa
                        await client.get_me()
                        logger.info("💓 Check-up automático realizado (Sistema Online/PC Independente)")
                    except Exception as e:
                        logger.error(f"Erro no polling: {e}")
                    
                    await asyncio.sleep(30)

            logger.info("🚀 MONITOR AUTÔNOMO INICIADO! (Pode desligar o PC agora)")
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
