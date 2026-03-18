"""
Bot de Alertas de Promoções — @alertas_andre_bot
"""
import logging
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.conf import settings
from asgiref.sync import sync_to_async
from bot.models import UserAlert
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
INACTIVITY_TIMEOUT = 60
INACTIVITY_JOB_KEY = 'inactivity_job'

# ─── Mensagem de boas-vindas ──────────────────────────────────────────────────
HELP_TEXT = (
    "🤖 *CENTRAL DE AJUDA E COMANDOS*\n\n"
    "Aqui você aprende como dominar o seu bot de alertas.\n\n"
    "1️⃣ *Pesquisa Simples*\n"
    "Basta digitar a palavra ou frase que deseja monitorar.\n"
    "Exemplo: `iphone 15` ou `notebook gamer`\n"
    "Porém esse *não é* o jeito mais *eficiente*.\n"
    "Caso queira algo mais avançado, veja a seguir.\n\n"
    "2️⃣ *Lógica de Pesquisa*\n"
    "O sistema usa uma lógica inteligente de filtros:\n"
    "• Use `+` para obrigar termos (Lógica E)\n"
    "• Use `/` para opções (Lógica OU)\n\n"
    "*Exemplos Práticos:*\n"
    "• Quero qualquer Samsung S23, S24 ou S25:\n"
    "`samsung+s23/s24/s25`\n"
    "_Traduzindo: Deve ter \"samsung\" E (\"s23\" ou \"s24\" ou \"s25\")_\n\n"
    "• Quero notebook gamer com RTX, mas só se for Dell ou Asus:\n"
    "`notebook+rtx+dell/asus`\n\n"
    "3️⃣ *Gerenciamento*\n"
    "Utilize os botões abaixo para gerenciar seus alertas sem precisar "
    "digitar comandos."
)

# ─── Teclados ─────────────────────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Nova Palavra", callback_data="add")],
        [InlineKeyboardButton("📋 Ver Minhas Palavras", callback_data="list")],
    ])

def modo_edicao_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ])

def pos_cadastro_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Adicionar Outro", callback_data="add"),
            InlineKeyboardButton("📋 Ver Lista", callback_data="list")
        ]
    ])

def lista_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Palavra", callback_data="add")],
        [InlineKeyboardButton("🗑 Remover um Alerta", callback_data="remove")],
        [InlineKeyboardButton("🔙 Menu Principal", callback_data="menu")],
    ])

# ─── ORM assíncrono ───────────────────────────────────────────────────────────
@sync_to_async
def db_get_or_create_alert(user_id, keyword, username, first_name):
    return UserAlert.objects.get_or_create(
        telegram_user_id=user_id,
        keyword=keyword,
        defaults={
            'telegram_username': username or '',
            'telegram_first_name': first_name or '',
            'is_active': True,
        }
    )

@sync_to_async
def db_get_user_alerts(user_id):
    return list(UserAlert.objects.filter(telegram_user_id=user_id, is_active=True))

@sync_to_async
def db_delete_alert(alert_id, user_id):
    return UserAlert.objects.filter(id=alert_id, telegram_user_id=user_id).delete()

@sync_to_async
def db_count_alerts(user_id):
    return UserAlert.objects.filter(telegram_user_id=user_id, is_active=True).count()

@sync_to_async
def db_activate_alert(alert):
    alert.is_active = True
    alert.save()

# ─── Timer de Inatividade ─────────────────────────────────────────────────────
def reset_inactivity_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if not context.job_queue:
        return
    old_job = context.user_data.get(INACTIVITY_JOB_KEY)
    if old_job:
        try:
            old_job.schedule_removal()
        except Exception:
            pass
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
            text="⏰ *Sessão encerrada por inatividade!*\n\nDigite /start para recomeçar. 👇",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erro inatividade: {e}")

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_keyword'] = False
    reset_inactivity_timer(context, update.effective_chat.id)
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

# ─── Callbacks dos botões ─────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    reset_inactivity_timer(context, chat_id)

    if data == "menu":
        context.user_data['waiting_keyword'] = False
        await query.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

    elif data == "add":
        context.user_data['waiting_keyword'] = True
        await query.message.reply_text(
            "✏️ *MODO DE EDIÇÃO*\n\n"
            "Digite as palavras chaves.\n"
            "Exemplo: `samsung+s23/s24`\n\n"
            "_Para cancelar, clique no botão abaixo_",
            parse_mode="Markdown",
            reply_markup=modo_edicao_keyboard()
        )

    elif data == "cancelar":
        context.user_data['waiting_keyword'] = False
        await query.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

    elif data == "list":
        alerts = await db_get_user_alerts(user_id)
        if not alerts:
            await query.message.reply_text(
                "📭 Você ainda não tem alertas cadastrados.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Adicionar Palavra", callback_data="add")]
                ])
            )
        else:
            text = "📋 *Seus alertas ativos:*\n\n"
            for i, a in enumerate(alerts, 1):
                text += f"{i}. `{a.keyword}`\n"
            text += "\n🔔 Você será notificado quando uma promo compatível aparecer!"
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=lista_keyboard())

    elif data == "remove":
        alerts = await db_get_user_alerts(user_id)
        if not alerts:
            await query.message.reply_text(
                "📭 Você não tem alertas para remover.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Voltar", callback_data="menu")]
                ])
            )
        else:
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

    elif data.startswith("del_"):
        keyword_id = int(data.replace("del_", ""))
        deleted, _ = await db_delete_alert(keyword_id, user_id)
        if deleted:
            await query.message.reply_text("✅ Alerta removido com sucesso!", reply_markup=lista_keyboard())
        else:
            await query.message.reply_text("❌ Alerta não encontrado.")

# ─── Mensagem de texto → salva palavra-chave ──────────────────────────────────
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    reset_inactivity_timer(context, chat_id)

    if text.startswith('/'):
        return

    if not context.user_data.get('waiting_keyword'):
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())
        return

    if len(text) < 2:
        await update.message.reply_text("❌ Palavra muito curta. Mínimo 2 caracteres.")
        return
    if len(text) > 200:
        await update.message.reply_text("❌ Palavra muito longa. Máximo 200 caracteres.")
        return

    try:
        alert, created = await db_get_or_create_alert(user.id, text, user.username, user.first_name)
        if not created and not alert.is_active:
            await db_activate_alert(alert)
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
    except Exception as e:
        logger.error(f"Erro ao salvar alerta: {e}")
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")

# ─── Inicializa o bot ─────────────────────────────────────────────────────────
def run_alert_bot():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ))

    logger.info("🤖 Bot de Alertas iniciado! @alertas_andre_bot")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    run_alert_bot()
