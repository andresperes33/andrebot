"""
Bot de Alertas de Promoções — @andreindica_bot
Usuários cadastram palavras-chave e recebem alertas quando
uma promo compatível é publicada no grupo do André.

Lógica de filtro:
  + = E  (obrigatório)
  / = OU (qualquer um)
  Exemplo: samsung+s23/s24/s25
  → tem "samsung" E tem ("s23" OU "s24" OU "s25")
"""
import asyncio
import logging
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.conf import settings
from bot.models import UserAlert
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

# ─── Texto de Ajuda ──────────────────────────────────────────────────────────
HELP_TEXT = """🤖 *CENTRAL DE AJUDA E COMANDOS*

Aqui você aprende como configurar seus alertas de promoções!

*1️⃣ Pesquisa Simples*
Basta digitar a palavra ou frase que deseja monitorar.
Exemplo: `iphone 15` ou `notebook gamer`

*2️⃣ Lógica de Pesquisa*
O sistema usa filtros inteligentes:
• Use `+` para obrigar termos (Lógica E)
• Use `/` para opções (Lógica OU)

*Exemplos Práticos:*
• Quero qualquer Samsung S23, S24 ou S25:
`samsung+s23/s24/s25`
_Traduzindo: Deve ter "samsung" E ("s23" ou "s24" ou "s25")_

• Quero notebook gamer com RTX, só se for Dell ou Asus:
`notebook+rtx+dell/asus`

*3️⃣ Gerenciamento*
Use os botões abaixo para gerenciar seus alertas!
"""

# ─── Teclado principal ────────────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Nova Palavra", callback_data="add")],
        [InlineKeyboardButton("📋 Ver Minhas Palavras", callback_data="list")],
        [InlineKeyboardButton("🗑 Remover Alerta", callback_data="remove")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="help")],
    ])

# ─── /start ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "amigo"
    await update.message.reply_text(
        f"👋 Olá, *{name}*! Bem-vindo ao bot de alertas de promoções!\n\n"
        "📢 Aqui você cadastra palavras-chave e eu te aviso no privado sempre que "
        "uma promoção compatível for publicada no grupo *André Indica*! 🔥\n\n"
        "Use os botões abaixo para começar:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ─── Callback dos botões ─────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help":
        await query.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

    elif data == "add":
        context.user_data['waiting_keyword'] = True
        await query.message.reply_text(
            "✏️ *Digite a palavra-chave* que deseja monitorar:\n\n"
            "Exemplos:\n"
            "• `airfryer`\n"
            "• `samsung+s25`\n"
            "• `notebook+rtx+dell/asus`",
            parse_mode="Markdown"
        )

    elif data == "list":
        await show_keywords(query, update.effective_user.id)

    elif data == "remove":
        await show_remove_menu(query, update.effective_user.id)

    elif data.startswith("del_"):
        keyword_id = int(data.replace("del_", ""))
        try:
            alert = UserAlert.objects.get(id=keyword_id, telegram_user_id=update.effective_user.id)
            keyword = alert.keyword
            alert.delete()
            await query.message.reply_text(f"✅ Alerta *{keyword}* removido!", parse_mode="Markdown", reply_markup=main_keyboard())
        except UserAlert.DoesNotExist:
            await query.message.reply_text("❌ Alerta não encontrado.", reply_markup=main_keyboard())

# ─── Lista as palavras-chave do usuário ──────────────────────────────────────
async def show_keywords(query, user_id):
    alerts = UserAlert.objects.filter(telegram_user_id=user_id, is_active=True)
    if not alerts.exists():
        await query.message.reply_text(
            "📭 Você ainda não tem alertas cadastrados.\n\nUse o botão abaixo para adicionar!",
            reply_markup=main_keyboard()
        )
        return

    text = "📋 *Suas palavras-chave de alerta:*\n\n"
    for i, alert in enumerate(alerts, 1):
        text += f"{i}. `{alert.keyword}`\n"
    text += "\nVocê receberá uma mensagem quando uma promoção compatível for publicada! 🔔"
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ─── Menu de remoção ─────────────────────────────────────────────────────────
async def show_remove_menu(query, user_id):
    alerts = UserAlert.objects.filter(telegram_user_id=user_id, is_active=True)
    if not alerts.exists():
        await query.message.reply_text("📭 Você não tem alertas para remover.", reply_markup=main_keyboard())
        return

    buttons = [
        [InlineKeyboardButton(f"🗑 {a.keyword}", callback_data=f"del_{a.id}")]
        for a in alerts
    ]
    buttons.append([InlineKeyboardButton("🔙 Voltar", callback_data="list")])
    await query.message.reply_text(
        "🗑 *Escolha qual alerta deseja remover:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── Recebe mensagem de texto (palavra-chave) ─────────────────────────────────
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().lower()

    # Ignora comandos
    if text.startswith('/'):
        return

    # Valida tamanho
    if len(text) < 2:
        await update.message.reply_text(
            "❌ Palavra muito curta. Digite pelo menos 2 caracteres.",
            reply_markup=main_keyboard()
        )
        return
    if len(text) > 200:
        await update.message.reply_text(
            "❌ Palavra muito longa. Máximo 200 caracteres.",
            reply_markup=main_keyboard()
        )
        return

    # Salva no banco automaticamente
    alert, created = UserAlert.objects.get_or_create(
        telegram_user_id=user.id,
        keyword=text,
        defaults={
            'telegram_username': user.username or '',
            'telegram_first_name': user.first_name or '',
            'is_active': True,
        }
    )

    if not created and not alert.is_active:
        alert.is_active = True
        alert.save()

    if created or not alert.is_active:
        await update.message.reply_text(
            f"✅ Alerta salvo com sucesso!\n\n"
            f"🔍 Palavra monitorada: `{text}`\n\n"
            f"Você será notificado no privado quando uma promoção compatível "
            f"aparecer no grupo *Alerta Tech Brasil*! 🔔",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"ℹ️ Você já está monitorando `{text}`!\n\n"
            f"Use *Ver Minhas Palavras* para ver todos os seus alertas ativos.",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    # Limpa estado de espera se existir
    context.user_data.pop('waiting_keyword', None)

# ─── Inicializa o bot ────────────────────────────────────────────────────────
def run_alert_bot():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", lambda u, c: u.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("🤖 Bot de Alertas iniciado! @andreindica_bot")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    run_alert_bot()
