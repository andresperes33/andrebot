import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.functions.channels import GetFullChannelRequest

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor zFinnY -> André Bot (Alta Velocidade "Humana")'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        bot_username = 'andreindica_bot'
        
        # ID exato do zFinnY Promos
        target_id = -1002216599534 

        async def main():
            # connection_retries elevado para manter a conexão ativa
            client = TelegramClient('session_monitor', api_id, api_hash, connection_retries=None)
            await client.start()
            
            # Cache simples para não repetir postagens
            processed_ids = set()

            logger.info(f"🚀 MONITOR DE ALTA VELOCIDADE ATIVO!")
            logger.info(f"🎯 Focado no zFinnY (ID: {target_id})")

            @client.on(events.NewMessage(chats=target_id))
            @client.on(events.MessageEdited(chats=target_id))
            async def event_handler(event):
                try:
                    msg_id = event.message.id
                    
                    if msg_id in processed_ids:
                        return

                    msg_text = event.message.message or ""
                    
                    # Log imediato assim que detecta
                    logger.info(f"⚡ DETECTADO AGORA: {msg_text[:30]}...")
                    
                    # Adiciona ao cache
                    processed_ids.add(msg_id)
                    if len(processed_ids) > 200:
                        processed_ids.clear()
                        processed_ids.add(msg_id)

                    # Encaminha na hora
                    await client.forward_messages(bot_username, event.message)
                    logger.info(f"✅ Encaminhado instantaneamente para @{bot_username}")
                    
                except Exception as e:
                    logger.error(f"Erro ao encaminhar: {e}")

            # Esta função simula um "humano" abrindo e olhando o grupo a cada 20 segundos
            # Isso força o Telegram a mandar as atualizações desse chat com prioridade máxima
            async def force_human_view():
                while True:
                    try:
                        # "Olha" para o canal (simula abrir o chat)
                        await client(GetFullChannelRequest(channel=target_id))
                        # Mantém a conexão TCP "quente"
                        await client.get_me()
                        logger.info("👀 Bot 'olhando' para o grupo zFinnY... (Conexão 100% quente)")
                    except Exception as e:
                        logger.warning(f"Aviso de conexão: {e}")
                    
                    await asyncio.sleep(20) # Repete a cada 20 segundos

            # Roda o monitor e a simulação humana juntos
            await asyncio.gather(
                client.run_until_disconnected(),
                force_human_view()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado.')
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
