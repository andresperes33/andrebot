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
    help = 'Monitor zFinnY -> André Bot (Radar Total Alta Velocidade)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        bot_username = 'andreindica_bot'

        async def main():
            # connection_retries=None mantém tentando reconectar sempre
            client = TelegramClient('session_monitor', api_id, api_hash, connection_retries=None)
            await client.start()
            
            logger.info("🔍 Procurando canal zFinnY nos seus chats...")
            target_id = None
            async for dialog in client.iter_dialogs():
                if "zFinnY" in dialog.name:
                    target_id = dialog.id
                    logger.info(f"✅ CANAL ALVO IDENTIFICADO: {dialog.name} (ID: {target_id})")
                    break

            if not target_id:
                logger.warning("⚠️ Não achei canal com nome 'zFinnY'. Usando ID padrão.")
                target_id = -1002216599534

            # Cache para evitar duplicidade
            processed_ids = set()

            # Listener Universal (escuta tudo e filtramos na mão para mais velocidade)
            @client.on(events.NewMessage)
            @client.on(events.MessageEdited)
            async def universal_handler(event):
                try:
                    # Se não for do canal que queremos, ignora na hora
                    if event.chat_id != target_id:
                        return
                    
                    msg_id = event.message.id
                    if msg_id in processed_ids:
                        return

                    msg_text = event.message.message or ""
                    logger.info(f"⚡ CAPTURADO DO zFinnY: {msg_text[:30]}...")

                    # Marca como enviado
                    processed_ids.add(msg_id)
                    if len(processed_ids) > 200:
                        processed_ids.clear()
                        processed_ids.add(msg_id)

                    # Encaminha o objeto da mensagem direto (é instantâneo)
                    await client.forward_messages(bot_username, event.message)
                    logger.info("✅ Encaminhado para o Bot!")
                except Exception as e:
                    logger.error(f"Erro no processamento: {e}")

            # Função "Pé no Acelerador"
            # Mantém a conexão com o Telegram 'pregada' na rede
            async def keep_alive():
                while True:
                    try:
                        # Pede o status do canal (força o Telegram a mandar atualizações)
                        await client(GetFullChannelRequest(channel=target_id))
                        # Ping na conta
                        await client.get_me()
                    except Exception:
                        pass
                    await asyncio.sleep(15) # A cada 15 segundos ele "cutuca" o Telegram

            logger.info("🚀 Radar de Alta Velocidade ATIVO e monitorando...")
            await asyncio.gather(
                client.run_until_disconnected(),
                keep_alive()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado.')
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
