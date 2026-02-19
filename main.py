import logging
import asyncio
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from news_fetcher import fetch_articles
from classifier import classify_article

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = "INSERISCI_TUO_TOKEN"
SEND_HOUR = 9  # ora invio automatico news
users_preferences = {}  # {user_id: {"macro":[], "branches":[]}}
scheduled_tasks = {}

# --- DOMINI & RAMI ---
MACRODOMAINS = {
    "Ingegneria": ["Elettronica", "Meccanica", "Biotecnologie", "Nanoelettronica", "Automazione"],
    "Finanza": ["Mercati", "Investimenti", "Criptovalute"],
    "Politica": ["Internazionale", "Locale", "Europea"]
}

# --- HELPERS ---
def get_user_prefs(user_id):
    if user_id not in users_preferences:
        users_preferences[user_id] = {"macro": [], "branches": []}
    return users_preferences[user_id]

# --- MENU INTERATTIVI ---
def build_macro_keyboard():
    keyboard = []
    for macro in MACRODOMAINS:
        keyboard.append([InlineKeyboardButton(macro, callback_data=f"macro:{macro}")])
    return InlineKeyboardMarkup(keyboard)

def build_branches_keyboard(user_id):
    prefs = get_user_prefs(user_id)
    keyboard = []
    for macro, branches in MACRODOMAINS.items():
        for b in branches:
            status = "✅" if b in prefs["branches"] else ""
            keyboard.append([InlineKeyboardButton(f"{b} {status}", callback_data=f"branch:{b}")])
    return InlineKeyboardMarkup(keyboard)

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Benvenuto! Usa i comandi:\n/domains\n/branches\n/sub_macro\n/sub_branches\n/uns_macro\n/uns_branches\n/preferences\n/all"
    )

async def domains(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Seleziona un macrodominio:", reply_markup=build_macro_keyboard()
    )

async def branches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Seleziona i rami:", reply_markup=build_branches_keyboard(update.message.from_user.id)
    )

async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = get_user_prefs(update.message.from_user.id)
    await update.message.reply_text(
        f"Preferenze attuali:\nMacro: {prefs['macro']}\nRami: {prefs['branches']}"
    )

async def all_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    articles = await fetch_articles()
    for art in articles[:5]:  # limit per debug
        await update.message.reply_text(f"{art['title']}\n{art['url']}")

# --- CALLBACK HANDLER ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    prefs = get_user_prefs(user_id)

    if data.startswith("macro:"):
        macro = data.split(":")[1]
        if macro not in prefs["macro"]:
            prefs["macro"].append(macro)
        await query.edit_message_text("Macrodomini aggiornati", reply_markup=build_macro_keyboard())

    if data.startswith("branch:"):
        branch = data.split(":")[1]
        if branch not in prefs["branches"]:
            prefs["branches"].append(branch)
        else:
            prefs["branches"].remove(branch)
        await query.edit_message_text("Rami aggiornati", reply_markup=build_branches_keyboard(user_id))

# --- SCHEDULING ---
async def send_daily_news(context: ContextTypes.DEFAULT_TYPE):
    articles = await fetch_articles()
    for user_id, prefs in users_preferences.items():
        user_articles = []
        for art in articles:
            art_macro, art_branch = classify_article(art["title"])
            if (not prefs["macro"] or art_macro in prefs["macro"]) and (
                not prefs["branches"] or art_branch in prefs["branches"]
            ):
                user_articles.append(f"{art['title']}\n{art['url']}")
        for msg in user_articles:
            await context.bot.send_message(chat_id=user_id, text=msg)

async def schedule_daily(app):
    now = datetime.now()
    target = datetime.combine(now.date(), time(hour=SEND_HOUR))
    if now > target:
        target += timedelta(days=1)
    delay = (target - now).total_seconds()
    await asyncio.sleep(delay)
    while True:
        await send_daily_news(app)
        await asyncio.sleep(24*60*60)

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("domains", domains))
    app.add_handler(CommandHandler("branches", branches))
    app.add_handler(CommandHandler("preferences", preferences))
    app.add_handler(CommandHandler("all", all_news))
    app.add_handler(CallbackQueryHandler(button))

    # scheduling background
    asyncio.create_task(schedule_daily(app))
    app.run_polling()

if __name__ == "__main__":
    main()
