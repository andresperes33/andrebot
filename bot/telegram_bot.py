import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from django.conf import settings
from .services import convert_to_affiliate_link, extract_links, get_product_info

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Pega o texto da mensagem ou a legenda da foto
    text = None
    photo = None
    
    if update.message.text:
        text = update.message.text
    elif update.message.caption:
        text = update.message.caption
        if update.message.photo:
            # Pega a foto na maior resolução disponível
            photo = update.message.photo[-1].file_id

    if not text:
        return

    links = extract_links(text)
    if not links:
        return

    modified_text = text
    affiliate_link = None
    original_link = None
    converted_any = False

    for link in links:
        is_shopee = 'shopee.com.br' in link or 's.shopee' in link
        is_aliexpress = 'aliexpress.com' in link or 's.click.aliexpress' in link
        is_ml = 'mercadolivre.com' in link or 'mlstatic.com' in link
        is_amazon = 'amazon.com.br' in link or 'amzn.to' in link
        is_kabum = 'kabum.com.br' in link or 'tidd.ly' in link
        is_telegram = 't.me/' in link
        is_tecnan = 'tecnan.com.br' in link

        if is_telegram or is_tecnan:
            # Troca qualquer link externo pelo seu site (fixo no settings)
            personal_link = settings.PERSONAL_CHANNEL_LINK
            if personal_link not in link:
                modified_text = modified_text.replace(link, personal_link)
                converted_any = True
            
            # Limpa nomes de outros canais pelo seu nome (fixo no settings)
            channel_name = settings.PERSONAL_CHANNEL_NAME
            modified_text = re.sub(r'(?i)zFinnY|CaCau|André Indica|Tecnan', channel_name, modified_text)
            continue

        if not is_shopee and not is_aliexpress and not is_ml and not is_amazon and not is_kabum:
            continue
        
        platform_name = "Shopee" if is_shopee else "AliExpress" if is_aliexpress else "Mercado Livre" if is_ml else "Amazon" if is_amazon else "Kabum/Awin"
        await update.message.reply_text(f"⏳ Processando {platform_name}...")

        converted = convert_to_affiliate_link(link)
        if not converted:
            await update.message.reply_text(f"❌ Não foi possível converter o link {platform_name}.")
            continue

        original_link = link
        affiliate_link = converted
        modified_text = modified_text.replace(link, converted)
        converted_any = True

    if not converted_any:
        return

    group_id = settings.TELEGRAM_GROUP_ID
    if not group_id:
        await update.message.reply_text("TELEGRAM_GROUP_ID não configurado.")
        return

    try:
        # Se a mensagem original já tinha foto, usamos a foto original
        if photo:
            await context.bot.send_photo(
                chat_id=group_id,
                photo=photo,
                caption=modified_text[:1024]
            )
        else:
            # Se não tinha foto, tentamos buscar uma da página (como fizemos antes)
            name, image_url, price = get_product_info(original_link)
            
            if image_url:
                await context.bot.send_photo(
                    chat_id=group_id,
                    photo=image_url,
                    caption=modified_text[:1024]
                )
            else:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=modified_text,
                    disable_web_page_preview=False
                )

        await update.message.reply_text("✅ Postado no grupo com o link de afiliado!")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao enviar: {e}")


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
