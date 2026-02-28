import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from django.conf import settings
from .services import convert_to_affiliate_link, extract_links, get_product_info

from .services import process_offer_to_group

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Precisamos guardar a aplicação globalmente ou passar no contexto para uso futuro
_bot_application = None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _bot_application
    
    text = None
    photo = None
    
    if update.message.text:
        text = update.message.text
    elif update.message.caption:
        text = update.message.caption
        if update.message.photo:
            photo = update.message.photo[-1].file_id

    if not text:
        return

    # Usamos a função de serviço que agora centraliza a lógica
    await update.message.reply_text("⏳ Processando oferta...")
    
    success = await process_offer_to_group(context.application, text, photo)
    
    if success:
        await update.message.reply_text("✅ Postado no grupo com o link de afiliado!")
    else:
        # Se falhou, pode ser que não tenha links monitorados ou erro na API
        pass


def start_bot():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "seu_token_aqui":
        print("Erro: TELEGRAM_BOT_TOKEN não configurado.")
        return

    application = ApplicationBuilder().token(token).build()
    
    # Agora aceita texto E fotos (com legenda)
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    
    print("Bot iniciado... Aguardando mensagens.")
    application.run_polling()
