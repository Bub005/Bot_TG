import os
import logging
import asyncio
from datetime import time as dtime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from news_fetcher import fetch_articles
from classifier import classify_article
from storage import Storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- CONFIG ---
SEND_HOUR = 9  # ora invio automatico news (locale del server)

# --- DOMINI & RAMI ---
MACRODOMAINS = {
    "Ingegneria": [
        "Elettronica",
        "Meccanica",
        "Biotecnologie",
        "Nanoelettronica",
        "Automazione",
    ],
    "Finanza": ["Mercati", "Investimenti", "Criptovalute"],
    "Politica": ["Internazionale", "Locale", "Europea"],
}


def build_macro_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    keyboard = []
    for macro in MACRODOMAINS:
        status = "✅" if macro in prefs["macro"] else ""
        keyboard.append(
            [InlineKeyboardButton(f"{macro} {status}".strip(), callback_data=f"macro:{macro}")]
        )
    keyboard.append([InlineKeyboardButton("Fine", callback_data="close")])
    return InlineKeyboardMarkup(keyboard)


def build_branches_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    keyboard = []
    for _, branches in MACRODOMAINS.items():
        for b in branches:
            status = "✅" if b in prefs["branches"] else ""
            keyboard.append(
                [InlineKeyboardButton(f"{b} {status}".strip(), callback_data=f"branch:{b}")]
            )
    keyboard.append([InlineKeyboardButton("Fine", callback_data="close")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto!\n\n"
        "Comandi:\n"
        "/domains - scegli macrodomini\n"
        "/branches - scegli rami\n"
        "/preferences - mostra preferenze\n"
        "/all - mostra alcune news\n\n"
        "Riceverai automaticamente le news ogni giorno se hai avviato il bot almeno una volta."
    )


async def domains(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.message.from_user.id
    prefs = storage.get_user_prefs(user_id)
    await update.message.reply_text("Seleziona un macrodominio:", reply_markup=build_macro_keyboard(prefs))


async def branches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.message.from_user.id
    prefs = storage.get_user_prefs(user_id)
    await update.message.reply_text("Seleziona i rami:", reply_markup=build_branches_keyboard(prefs))


async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.message.from_user.id
    prefs = storage.get_user_prefs(user_id)
    await update.message.reply_text(
        f"Preferenze attuali:\nMacro: {prefs['macro']}\nRami: {prefs['branches']}"
    )


async def all_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    articles = await fetch_articles()
    if not articles:
        await update.message.reply_text("Nessun articolo trovato.")
        return
    for art in articles[:5]:
        await update.message.reply_text(f"{art['title']}\n{art['url']}")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data == "close":
        await query.edit_message_text("Ok.")
        return

    prefs = storage.get_user_prefs(user_id)

    if data.startswith("macro:"):
        macro = data.split(":", 1)[1]
        prefs = storage.toggle_macro(user_id, macro)
        await query.edit_message_text(
            "Macrodomini aggiornati (clicca per attivare/disattivare):",
            reply_markup=build_macro_keyboard(prefs),
        )
        return

    if data.startswith("branch:"):
        branch = data.split(":", 1)[1]
        prefs = storage.toggle_branch(user_id, branch)
        await query.edit_message_text(
            "Rami aggiornati (clicca per attivare/disattivare):",
            reply_markup=build_branches_keyboard(prefs),
        )
        return


async def send_daily_news_job(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue callback: invia news filtrate a tutti gli utenti salvati."""
    storage: Storage = context.application.bot_data["storage"]

    articles = await fetch_articles()
    if not articles:
        return

    users = storage.list_users()
    for user_id in users:
        prefs = storage.get_user_prefs(user_id)
        user_msgs = []
        for art in articles:
            art_macro, art_branch = classify_article(art["title"])
            if (not prefs["macro"] or art_macro in prefs["macro"]) and (
                not prefs["branches"] or art_branch in prefs["branches"]
            ):
                user_msgs.append(f"{art['title']}\n{art['url']}")

        for msg in user_msgs:
            try:
                await context.bot.send_message(chat_id=user_id, text=msg)
            except Exception:
                logger.exception("Errore invio messaggio a user_id=%s", user_id)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Variabile d'ambiente BOT_TOKEN mancante. Esegui: export BOT_TOKEN='...'" )

    app = ApplicationBuilder().token(token).build()

    # storage persistente
    storage = Storage("bot.db")
    app.bot_data["storage"] = storage

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("domains", domains))
    app.add_handler(CommandHandler("branches", branches))
    app.add_handler(CommandHandler("preferences", preferences))
    app.add_handler(CommandHandler("all", all_news))
    app.add_handler(CallbackQueryHandler(button))

    # job giornaliero
    app.job_queue.run_daily(send_daily_news_job, time=dtime(hour=SEND_HOUR, minute=0, second=0))

    app.run_polling()


if __name__ == "__main__":
    main()
