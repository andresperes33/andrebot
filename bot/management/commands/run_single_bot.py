"""
Bot único do Telegram: junta o processamento de ofertas (DM) com o cadastro de
alertas de promoções num ÚNICO aplicativo. Isso evita o erro
'Conflict: terminated by other getUpdates request' — o Telegram só aceita UMA
conexão de getUpdates por token.
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from telegram import MessageEntity
from telegram.error import Conflict, TelegramError
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters,
)

from bot.alert_bot import button_handler, message_handler as alert_message_handler, start as alert_start
from bot.telegram_bot import handle_message as offer_handle_message

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Inicia o bot único do Telegram (alertas + ofertas) sem Conflict de getUpdates.'

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            self.stdout.write(self.style.ERROR('TELEGRAM_BOT_TOKEN não configurado!'))
            return

        app = ApplicationBuilder().token(token).build()

        # Alertas: comandos e mensagens de cadastro (texto puro, sem URL)
        app.add_handler(CommandHandler('start', alert_start, filters=filters.ChatType.PRIVATE))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & ~filters.Entity(MessageEntity.URL),
            alert_message_handler
        ))

        # Ofertas: mensagens com URL ou foto (DM) → converte link e publica
        offer_filter = ((filters.TEXT & filters.Entity(MessageEntity.URL)) | filters.PHOTO)
        app.add_handler(MessageHandler(offer_filter & filters.ChatType.PRIVATE, offer_handle_message))

        async def error_handler(update, context):
            if isinstance(context.error, Conflict):
                logger.warning('⚠️ Telegram 409 Conflict: outra sessão/container estava com getUpdates ativo. Reconectando...')
            else:
                logger.error(f'❌ Exceção capturada no bot: {context.error}', exc_info=context.error)

        app.add_error_handler(error_handler)

        logger.info('🤖 Bot único do Telegram iniciado (alertas + ofertas).')

        # Retry com backoff: durante deploy do Easypanel o container antigo ainda
        # fica de pé por alguns segundos — o Conflict derruba o polling se
        # acontecer; ao invés de morrer, espera e tenta de novo.
        tentativa = 0
        while True:
            try:
                app.run_polling(drop_pending_updates=True)
                break
            except Conflict:
                tentativa += 1
                delay = min(30, 5 * tentativa)
                logger.warning(f'⚠️ Conflict (outra instância ativa). Nova tentativa em {delay}s... (tentativa {tentativa})')
                time.sleep(delay)
            except TelegramError as e:
                logger.error(f'❌ Erro do Telegram no polling: {e}')
                time.sleep(10)
            except KeyboardInterrupt:
                logger.info('Bot parado.')
                break
            except Exception as e:
                logger.error(f'❌ Erro inesperado no polling: {e}')
                time.sleep(10)