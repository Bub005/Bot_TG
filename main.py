import os
import json
import feedparser
from datetime import datetime, time
from newspaper import Article
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

TOKEN = os.environ["BOT_TOKEN"]

USERS_FILE = "users.json"
LAST_SENT_FILE = "last_sent.json"

RSS_FEEDS = [
    "https://spectrum.ieee.org/rss/fulltext",
    "https://news.mit.edu/rss/topic/engineering",
    "https://www.sciencedaily.com/rss/engineering.xml"
]

# =========================
# DOMAINS STRUCTURE
# =========================

MACRO_DOMAINS = {
    "Ingegneria": {
        "Robotica": {
            "positive": ["robot", "automation", "industrial", "servo", "actuator", "manufacturing"],
            "negative": ["military", "war", "missile", "army", "conflict"],
            "threshold": 2
        },
        "Automazione": {
            "positive": ["plc", "control system", "factory", "automation", "industry 4.0"],
            "negative": ["politics", "war"],
            "threshold": 2
        },
        "Energia": {
            "positive": ["renewable", "solar", "wind", "battery", "grid", "power system"],
            "negative": ["oil war", "geopolitical"],
            "threshold": 2
        },
        "Biotech": {
            "positive": ["biotech", "genetic", "biomedical", "synthetic biology"],
            "negative": ["political regulation"],
            "threshold": 1
        },
        "Nanoelettronica": {
            "positive": ["nanotech", "semiconductor", "chip", "transistor", "graphene"],
            "negative": ["trade war"],
            "threshold": 1
        }
    }
}

GLOBAL_BLACKLIST = [
    "election", "president", "government", "parliament"
]

# =========================
# FILE UTILS
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
