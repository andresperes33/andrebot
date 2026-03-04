"""
Bot de Alertas de Promoções — @andreindica_bot
"""
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
INACTIVITY_TIMEOUT = 60  # segundos
INACTIVITY_JOB_KEY = 'inactivity_job'


# ─── Timer de Inatividade ────────────────────────────────────────────────────
def reset_inactivity_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    old_job = context.user_data.get(INACTIVITY_JOB_KEY)
    if old_job:
        old_job.schedule_removal()
    job = context.job_queue.run_once(
        inactivity_callback,
        when=INACTIVITY_TIMEOUT,
        chat_id=chat_id,
        user_id=chat_id,
        data={'chat_id': chat_id}
    )
    context.user_data[INACTIVITY_JOB_KEY] = job


async def inactivity_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data['chat_id']
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⏰ *Sessão encerrada por inatividade!*\n\n"
                "Você ficou 1 minuto sem interagir.\n"
                "Digite /start para recomeçar."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erro no callback de inatividade: {e}")


# ─── Teclados ────────────────────────────────────────────────────────────────
def modo_edicao_keyboard():
    """Teclado exibido no MODO DE EDIÇÃO."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ])


def pos_cadastro_keyboard():
    """Teclado após salvar uma palavra-chave."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Adicionar Outro", callback_data="add"),
            InlineKeyboardButton("📋 Ver Lista", callback_data="list")
        ]
    ])


def lista_keyboard():
    """Teclado da lista de palavras."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Palavra", callback_data="add")],
        [InlineKeyboardButton("🗑 Remover um Alerta", callback_data="remove")],
    ])


# ─── Mensagem MODO DE EDIÇÃO ──────────────────────────────────────────────────
async def send_modo_edicao(target, context, chat_id):
    """Envia a mensagem de modo de edição e ativa o estado de espera."""
    context.user_data['waiting_keyword'] = True
    reset_inactivity_timer(context, chat_id)

    text = (
        "✏️ *MODO DE EDIÇÃO*\n\n"
        "Digite a palavra-chave que deseja monitorar.\n"
        "Exemplo: `samsung+s23/s24`\n\n"
        "_Para cancelar, clique no botão abaixo_"
    )
    if hasattr(target, 'message'):
        # É um Update normal
        await target.message.reply_text(text, parse_mode="Markdown", reply_markup=modo_edicao_keyboard())
    else:
        # É um CallbackQuery
        await target.message.reply_text(text, parse_mode="Markdown", reply_markup=modo_edicao_keyboard())


# ─── /start ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_modo_edicao(update, context, update.effective_chat.id)


# ─── Callback dos botões ─────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    reset_inactivity_timer(context, chat_id)

    if data == "add":
        # Volta ao modo de edição
        context.user_data['waiting_keyword'] = True
        await query.message.reply_text(
            "✏️ *MODO DE EDIÇÃO*\n\n"
            "Digite a palavra-chave que deseja monitorar.\n"
            "Exemplo: `samsung+s23/s24`\n\n"
            "_Para cancelar, clique no botão abaixo_",
            parse_mode="Markdown",
            reply_markup=modo_edicao_keyboard()
        )

    elif data == "cancelar":
        context.user_data['waiting_keyword'] = False
        alerts = UserAlert.objects.filter(telegram_user_id=user_id, is_active=True)
        count = alerts.count()
        await query.message.reply_text(
            f"✅ Modo de edição encerrado.\n\n"
            f"Você tem *{count}* alerta(s) ativo(s).\n"
            f"Digite /start para voltar ao menu.",
            parse_mode="Markdown"
        )

    elif data == "list":
        await show_keywords(query, user_id)

    elif data == "remove":
        await show_remove_menu(query, user_id)

    elif data.startswith("del_"):
        keyword_id = int(data.replace("del_", ""))
        try:
            alert = UserAlert.objects.get(id=keyword_id, telegram_user_id=user_id)
            keyword = alert.keyword
            alert.delete()
            await query.message.reply_text(
                f"✅ Alerta `{keyword}` removido!",
                parse_mode="Markdown",
                reply_markup=lista_keyboard()
            )
        except UserAlert.DoesNotExist:
            await query.message.reply_text("❌ Alerta não encontrado.")


# ─── Lista de palavras-chave ──────────────────────────────────────────────────
async def show_keywords(query, user_id):
    alerts = UserAlert.objects.filter(telegram_user_id=user_id, is_active=True)
    if not alerts.exists():
        await query.message.reply_text(
            "📭 Você ainda não tem alertas cadastrados.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Adicionar Palavra", callback_data="add")]
            ])
        )
        return

    text = "📋 *Seus alertas ativos:*\n\n"
    for i, alert in enumerate(alerts, 1):
        text += f"{i}. `{alert.keyword}`\n"
    text += "\n🔔 Você será notificado quando uma promo compatível aparecer!"
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=lista_keyboard())


# ─── Menu de remoção ─────────────────────────────────────────────────────────
async def show_remove_menu(query, user_id):
    alerts = UserAlert.objects.filter(telegram_user_id=user_id, is_active=True)
    if not alerts.exists():
        await query.message.reply_text("📭 Você não tem alertas para remover.")
        return

    buttons = [
        [InlineKeyboardButton(f"🗑 {a.keyword}", callback_data=f"del_{a.id}")]
        for a in alerts
    ]
    buttons.append([InlineKeyboardButton("🔙 Voltar", callback_data="list")])
    await query.message.reply_text(
        "🗑 *Escolha qual alerta remover:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ─── Recebe texto (palavra-chave) ────────────────────────────────────────────
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    reset_inactivity_timer(context, chat_id)

    if text.startswith('/'):
        return

    # Só salva se estiver no modo de edição
    if not context.user_data.get('waiting_keyword'):
        await send_modo_edicao(update, context, chat_id)
        return

    # Valida tamanho
    if len(text) < 2:
        await update.message.reply_text("❌ Palavra muito curta. Digite pelo menos 2 caracteres.")
        return
    if len(text) > 200:
        await update.message.reply_text("❌ Palavra muito longa. Máximo 200 caracteres.")
        return

    # Salva no banco
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
        created = True

    context.user_data['waiting_keyword'] = False

    if created:
        await update.message.reply_text(
            f"✅ *Sucesso!*\nO termo `{text}` foi adicionado.",
            parse_mode="Markdown",
            reply_markup=pos_cadastro_keyboard()
        )
    else:
        await update.message.reply_text(
            f"ℹ️ O termo `{text}` já está na sua lista!",
            parse_mode="Markdown",
            reply_markup=pos_cadastro_keyboard()
        )


# ─── Inicializa o bot ────────────────────────────────────────────────────────
def run_alert_bot():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Só responde em DM (chat privado)
    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ))

    logger.info("🤖 Bot de Alertas iniciado! @andreindica_bot")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    run_alert_bot()
