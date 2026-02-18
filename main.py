import feedparser
import asyncio
import os
import json
from datetime import time as dt_time
from newspaper import Article
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
from telegram.constants import ParseMode

from sentence_transformers import SentenceTransformer, util
import torch

# ================= CONFIG =================

TOKEN = "8374523039:AAEwMlQ0_4bm6Wa-536UMYk80gTuA_Kgo5c"

RSS_FEEDS = [
    "https://spectrum.ieee.org/feed",
    "https://www.technologyreview.com/feed/",
    "https://phys.org/rss-feed/",
    "https://www.automationworld.com/rss",
    "https://www.rinnovabili.it/feed/"
]

DATA_FILE = "database.json"

CATEGORY_DESCRIPTIONS = {
    "AI": "artificial intelligence machine learning deep learning neural networks large language models",
    "Automazione": "industrial automation plc control systems mechatronics factory robotics systems",
    "Automotive": "electric vehicles batteries automotive self driving mobility transportation systems",
    "Energia": "renewable energy solar wind hydrogen sustainability smart grid power systems",
    "Materiali": "advanced materials nanotechnology semiconductors graphene composite materials physics",
    "Robotica": "robotics humanoid robots drones automation mechanical systems engineering"
}

# ================= AI MODEL =================

print("Caricamento modello AI...")
model = SentenceTransformer("all-MiniLM-L6-v2")

category_embeddings = {
    cat: model.encode(desc, convert_to_tensor=True)
    for cat, desc in CATEGORY_DESCRIPTIONS.items()
}
print("Modello pronto.")

def classify_article_semantic(text):
    article_embedding = model.encode(text, convert_to_tensor=True)
    scores = {}

    for cat, emb in category_embeddings.items():
        score = util.cos_sim(article_embedding, emb)
        scores[cat] = float(score)

    best = max(scores, key=scores.get)

    if scores[best] > 0.35:
        return best
    return None

# ================= DATABASE =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "history": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ================= UI =================

def build_keyboard(user_prefs):
    keyboard = []
    for cat in CATEGORY_DESCRIPTIONS.keys():
        label = f"✔ {cat}" if cat in user_prefs else cat
        keyboard.append([InlineKeyboardButton(label, callback_data=cat)])

    keyboard.append([InlineKeyboardButton("🔄 Aggiorna News Ora", callback_data="refresh")])
    return InlineKeyboardMarkup(keyboard)

# ================= NEWS =================

async def summarize(url):
    try:
        article = Article(url)
        await asyncio.to_thread(article.download)
        await asyncio.to_thread(article.parse)

        text = article.text
        summary = " ".join(text.split(". ")[:4])

        return article.title, summary
    except:
        return None, None

async def scan_news(context, chat_id=None):
    data = load_data()

    users = data["users"]
    history = data["history"]

    targets = [chat_id] if chat_id else users.keys()

    for feed_url in RSS_FEEDS:
        print("Scanning:", feed_url)
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:10]:

            for uid in targets:

                uid = str(uid)

                if uid not in history:
                    history[uid] = []

                if entry.link in history[uid]:
                    continue

                title, summary = await summarize(entry.link)
                if not title:
                    continue

                category = classify_article_semantic(title + " " + summary)
                print("Articolo:", title[:40], "| Categoria:", category)

                if not category:
                    continue

                if category not in users.get(uid, []):
                    continue

                message = (
                    f"📌 <b>{title}</b>\n"
                    f"🏷 Categoria: {category}\n\n"
                    f"{summary}\n\n"
                    f"<a href='{entry.link}'>Leggi tutto</a>"
                )

                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )
                    history[uid].append(entry.link)
                    save_data(data)
                    await asyncio.sleep(1)
                except Exception as e:
                    print("Errore invio:", e)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_chat.id)

    if uid not in data["users"]:
        data["users"][uid] = []
        data["history"][uid] = []

    save_data(data)

    await update.message.reply_text(
        "🤖 Bot AI Tech Intelligence attivo!\nUsa /categorie per scegliere gli argomenti."
    )

async def categorie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_chat.id)

    if uid not in data["users"]:
        data["users"][uid] = []

    keyboard = build_keyboard(data["users"][uid])

    await update.message.reply_text(
        "Seleziona le categorie:",
        reply_markup=keyboard
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    uid = str(query.message.chat.id)

    if query.data == "refresh":
        await scan_news(context, uid)
        return

    if uid not in data["users"]:
        data["users"][uid] = []

    category = query.data

    if category in data["users"][uid]:
        data["users"][uid].remove(category)
    else:
        data["users"][uid].append(category)

    save_data(data)

    keyboard = build_keyboard(data["users"][uid])
    await query.edit_message_reply_markup(reply_markup=keyboard)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await scan_news(context, update.effective_chat.id)

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("categorie", categorie))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CallbackQueryHandler(button_handler))

    if app.job_queue:
        async def job(context):
            await scan_news(context)

        app.job_queue.run_daily(job, time=dt_time(8, 00))

    print("BOT MAX LEVEL AVVIATO")
    app.run_polling()

if __name__ == "__main__":
    main()
