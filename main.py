import json
import os
import feedparser
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

TOKEN = "INSERISCI_IL_TUO_TOKEN"

USERS_FILE = "users.json"
LAST_SENT_FILE = "last_sent.json"

RSS_FEEDS = [
    "https://news.mit.edu/rss/topic/engineering",
    "https://spectrum.ieee.org/rss/fulltext",
    "https://www.sciencedaily.com/rss/computers_math.xml"
]

BLACKLIST_WORDS = [
    "war", "military", "missile", "election",
    "government", "conflict", "politics"
]

MACRO_DOMAINS = {
    "Ingegneria": [
        "Civile",
        "Meccanica",
        "Elettronica",
        "Nanoelettronica",
        "Automazione",
        "Robotica",
        "Biotech",
        "Materiali",
        "Energia",
        "Macchine Automatiche"
    ]
}

# =========================
# UTILITY FILE MANAGEMENT
# =========================

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def ensure_user(user_id):
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "macro": [],
            "branches": [],
            "all_mode": False
        }
        save_json(USERS_FILE, users)

# =========================
# DOMAINS COMMAND
# =========================

async def domains(update, context):
    keyboard = []
    for macro in MACRO_DOMAINS:
        keyboard.append([InlineKeyboardButton(
            macro,
            callback_data=f"macro_{macro}"
        )])

    await update.message.reply_text(
        "Seleziona MacroDominio:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK HANDLER
# =========================

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    ensure_user(user_id)

    users = load_json(USERS_FILE)
    data = query.data

    if data.startswith("macro_"):
        macro = data.replace("macro_", "")
        keyboard = []

        for branch in MACRO_DOMAINS[macro]:
            keyboard.append([
                InlineKeyboardButton(
                    branch,
                    callback_data=f"toggle_{macro}_{branch}"
                )
            ])

        keyboard.append([InlineKeyboardButton("⬅ Indietro", callback_data="back")])

        await query.edit_message_text(
            f"Macro: {macro}\nSeleziona rami (toggle attivo/disattivo)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("toggle_"):
        _, macro, branch = data.split("_", 2)

        if macro not in users[str(user_id)]["macro"]:
            users[str(user_id)]["macro"].append(macro)

        if branch in users[str(user_id)]["branches"]:
            users[str(user_id)]["branches"].remove(branch)
            msg = f"{branch} rimosso ❌"
        else:
            users[str(user_id)]["branches"].append(branch)
            msg = f"{branch} aggiunto ✅"

        save_json(USERS_FILE, users)
        await query.answer(msg, show_alert=True)

    elif data == "back":
        await domains(update, context)

# =========================
# PREFERENCES
# =========================

async def preferences(update, context):
    user_id = update.message.from_user.id
    ensure_user(user_id)

    users = load_json(USERS_FILE)
    data = users[str(user_id)]

    await update.message.reply_text(
        f"Macro:\n{', '.join(data['macro']) or 'Nessuno'}\n\n"
        f"Rami:\n{', '.join(data['branches']) or 'Nessuno'}\n\n"
        f"All Mode: {data['all_mode']}"
    )

# =========================
# ALL MODE
# =========================

async def all_command(update, context):
    user_id = update.message.from_user.id
    ensure_user(user_id)

    users = load_json(USERS_FILE)

    users[str(user_id)]["all_mode"] = not users[str(user_id)]["all_mode"]
    save_json(USERS_FILE, users)

    status = users[str(user_id)]["all_mode"]

    await update.message.reply_text(
        f"Modalità ALL {'ATTIVA 🔥' if status else 'DISATTIVATA ❌'}"
    )

# =========================
# ARTICLE FILTER
# =========================

def is_blacklisted(text):
    text = text.lower()
    return any(word in text for word in BLACKLIST_WORDS)

def branch_match(text, branches):
    text = text.lower()
    for branch in branches:
        if branch.lower() in text:
            return True
    return False

# =========================
# SEND NEWS
# =========================

async def send_news(context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USERS_FILE)
    last_sent = load_json(LAST_SENT_FILE)
    today = datetime.now().strftime("%Y-%m-%d")

    for user_id, prefs in users.items():

        if last_sent.get(user_id) == today:
            continue

        articles_sent = 0

        for feed_url in RSS_FEEDS:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:5]:
                text = f"{entry.title} {entry.get('summary','')}"

                if is_blacklisted(text):
                    continue

                if not prefs["all_mode"]:
                    if not branch_match(text, prefs["branches"]):
                        continue

                message = f"📰 {entry.title}\n{entry.link}"

                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=message
                )

                articles_sent += 1

        last_sent[user_id] = today
        save_json(LAST_SENT_FILE, last_sent)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("domains", domains))
    app.add_handler(CommandHandler("preferences", preferences))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    # invio automatico ogni giorno alle 8
    app.job_queue.run_daily(
        send_news,
        time=datetime.strptime("08:00", "%H:%M").time()
    )

    print("Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()
