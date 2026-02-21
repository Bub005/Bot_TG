import logging
import os
from datetime import time as dtime
from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from classifier import classify_article
from news_fetcher import fetch_articles
from rate_limit import RateLimiter
from storage import Storage

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SEND_HOUR: int = int(os.getenv("SEND_HOUR", "9"))
PAGE_SIZE: int = 5
MAX_DIGEST_ITEMS: int = int(os.getenv("MAX_DIGEST_ITEMS", "20"))
ADMIN_CHAT_ID: int | None = (
    int(_admin_id) if (_admin_id := os.getenv("ADMIN_CHAT_ID")) else None
)

# ---------------------------------------------------------------------------
# Domain / branch structure
# ---------------------------------------------------------------------------
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

ALL_MACROS: List[str] = list(MACRODOMAINS.keys())
ALL_BRANCHES: List[str] = [b for bs in MACRODOMAINS.values() for b in bs]

# ---------------------------------------------------------------------------
# Rate limiters
# ---------------------------------------------------------------------------
CMD_LIMITER = RateLimiter(max_calls=5, window_seconds=30)
CB_LIMITER = RateLimiter(max_calls=15, window_seconds=30)

# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------

def _build_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 Macrodomini", callback_data="open_macro"),
                InlineKeyboardButton("🔀 Rami", callback_data="open_branch"),
            ],
            [
                InlineKeyboardButton("📋 Preferenze", callback_data="show_prefs"),
                InlineKeyboardButton("📰 News Ora", callback_data="news_now"),
            ],
            [InlineKeyboardButton("🔄 Reset preferenze", callback_data="reset_prefs")],
        ]
    )


def _build_macro_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    rows = []
    for macro in ALL_MACROS:
        tick = "✅ " if macro in prefs["macro"] else ""
        rows.append(
            [InlineKeyboardButton(f"{tick}{macro}", callback_data=f"macro:{macro}")]
        )
    rows.append(
        [
            InlineKeyboardButton("✔ Tutti", callback_data="sel_all_m"),
            InlineKeyboardButton("✖ Nessuno", callback_data="sel_none_m"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🔄 Reset", callback_data="reset_prefs"),
            InlineKeyboardButton("✅ Fine", callback_data="close"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _build_branch_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    rows = []
    for macro, branches in MACRODOMAINS.items():
        row = []
        for b in branches:
            tick = "✅ " if b in prefs["branches"] else ""
            row.append(
                InlineKeyboardButton(f"{tick}{b}", callback_data=f"branch:{b}")
            )
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append(
        [
            InlineKeyboardButton("✔ Tutti", callback_data="sel_all_b"),
            InlineKeyboardButton("✖ Nessuno", callback_data="sel_none_b"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🔄 Reset", callback_data="reset_prefs"),
            InlineKeyboardButton("✅ Fine", callback_data="close"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _build_news_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prec", callback_data=f"news_p:{page - 1}"))
    nav.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Succ ➡", callback_data=f"news_p:{page + 1}"))
    return InlineKeyboardMarkup([nav])


def _escape_title(title: str) -> str:
    """Strip MarkdownV2-unsafe chars from an article title."""
    return title.replace("*", "").replace("[", "").replace("]", "")


def _format_news_page(articles: List[dict], page: int) -> str:
    total = len(articles)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    chunk = articles[start : start + PAGE_SIZE]
    lines = [f"📰 *News — pagina {page + 1}/{total_pages}*\n"]
    for i, art in enumerate(chunk, start=1):
        title = _escape_title(art["title"])
        lines.append(f"{start + i}\\. [{title}]({art['url']})")
    return "\n".join(lines)


def _format_digest(articles: List[dict]) -> str:
    lines = [f"📰 *Digest giornaliero — {len(articles)} articoli*\n"]
    for i, art in enumerate(articles, 1):
        title = _escape_title(art["title"])
        lines.append(f"{i}\\. [{title}]({art['url']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Benvenuto nel Bot News!*\n\n"
        "Scegli un'opzione dal menu:"
    )
    if update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_build_menu_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_build_menu_keyboard(),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    storage.get_user_prefs(update.effective_user.id)  # ensure user is registered
    await _show_menu(update, context)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    await _show_menu(update, context)


async def domains(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    storage: Storage = context.application.bot_data["storage"]
    prefs = storage.get_user_prefs(update.message.from_user.id)
    await update.message.reply_text(
        "Seleziona i macrodomini di interesse:",
        reply_markup=_build_macro_keyboard(prefs),
    )


async def branches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    storage: Storage = context.application.bot_data["storage"]
    prefs = storage.get_user_prefs(update.message.from_user.id)
    await update.message.reply_text(
        "Seleziona i rami di interesse:",
        reply_markup=_build_branch_keyboard(prefs),
    )


async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    storage: Storage = context.application.bot_data["storage"]
    prefs = storage.get_user_prefs(update.message.from_user.id)
    macro_str = ", ".join(prefs["macro"]) if prefs["macro"] else "tutte"
    branch_str = ", ".join(prefs["branches"]) if prefs["branches"] else "tutti"
    await update.message.reply_text(
        f"📋 *Preferenze attuali*\n\nMacro: {macro_str}\nRami: {branch_str}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    storage: Storage = context.application.bot_data["storage"]
    storage.reset_user_prefs(update.message.from_user.id)
    await update.message.reply_text("✅ Preferenze resettate.")


async def all_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CMD_LIMITER.is_allowed(update.effective_user.id):
        await update.message.reply_text("⏳ Troppi comandi. Riprova tra qualche secondo.")
        return
    msg = await update.message.reply_text("⏳ Recupero articoli…")
    articles = await fetch_articles()
    if not articles:
        await msg.edit_text("Nessun articolo trovato.")
        return
    context.user_data["news_articles"] = articles
    text = _format_news_page(articles, 0)
    await msg.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_build_news_keyboard(0, len(articles)),
        disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not CB_LIMITER.is_allowed(user_id):
        await query.answer("⏳ Troppi click. Riprova.", show_alert=True)
        return

    storage: Storage = context.application.bot_data["storage"]
    data = query.data

    # ---- noop ----
    if data == "noop":
        return

    # ---- menu ----
    if data == "menu":
        await _show_menu(update, context)
        return

    # ---- close ----
    if data == "close":
        await query.edit_message_text("✅ Ok.")
        return

    # ---- show preferences ----
    if data == "show_prefs":
        prefs = storage.get_user_prefs(user_id)
        macro_str = ", ".join(prefs["macro"]) if prefs["macro"] else "tutte"
        branch_str = ", ".join(prefs["branches"]) if prefs["branches"] else "tutti"
        await query.edit_message_text(
            f"📋 Macro: {macro_str}\nRami: {branch_str}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
            ),
        )
        return

    # ---- open macro selector ----
    if data == "open_macro":
        prefs = storage.get_user_prefs(user_id)
        await query.edit_message_text(
            "Seleziona i macrodomini:",
            reply_markup=_build_macro_keyboard(prefs),
        )
        return

    # ---- open branch selector ----
    if data == "open_branch":
        prefs = storage.get_user_prefs(user_id)
        await query.edit_message_text(
            "Seleziona i rami:",
            reply_markup=_build_branch_keyboard(prefs),
        )
        return

    # ---- reset preferences ----
    if data == "reset_prefs":
        storage.reset_user_prefs(user_id)
        await query.edit_message_text(
            "✅ Preferenze resettate.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Menu", callback_data="menu")]]
            ),
        )
        return

    # ---- select all / none macros ----
    if data == "sel_all_m":
        prefs = storage.set_all_macro(user_id, ALL_MACROS)
        await query.edit_message_text(
            "Seleziona i macrodomini:", reply_markup=_build_macro_keyboard(prefs)
        )
        return
    if data == "sel_none_m":
        prefs = storage.set_all_macro(user_id, [])
        await query.edit_message_text(
            "Seleziona i macrodomini:", reply_markup=_build_macro_keyboard(prefs)
        )
        return

    # ---- select all / none branches ----
    if data == "sel_all_b":
        prefs = storage.set_all_branches(user_id, ALL_BRANCHES)
        await query.edit_message_text(
            "Seleziona i rami:", reply_markup=_build_branch_keyboard(prefs)
        )
        return
    if data == "sel_none_b":
        prefs = storage.set_all_branches(user_id, [])
        await query.edit_message_text(
            "Seleziona i rami:", reply_markup=_build_branch_keyboard(prefs)
        )
        return

    # ---- toggle macro ----
    if data.startswith("macro:"):
        macro = data.split(":", 1)[1]
        prefs = storage.toggle_macro(user_id, macro)
        await query.edit_message_text(
            "Seleziona i macrodomini:", reply_markup=_build_macro_keyboard(prefs)
        )
        return

    # ---- toggle branch ----
    if data.startswith("branch:"):
        branch = data.split(":", 1)[1]
        prefs = storage.toggle_branch(user_id, branch)
        await query.edit_message_text(
            "Seleziona i rami:", reply_markup=_build_branch_keyboard(prefs)
        )
        return

    # ---- news now (from menu) ----
    if data == "news_now":
        await query.edit_message_text("⏳ Recupero articoli…")
        articles = await fetch_articles()
        if not articles:
            await query.edit_message_text("Nessun articolo trovato.")
            return
        context.user_data["news_articles"] = articles
        text = _format_news_page(articles, 0)
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_build_news_keyboard(0, len(articles)),
            disable_web_page_preview=True,
        )
        return

    # ---- news pagination ----
    if data.startswith("news_p:"):
        page = int(data.split(":", 1)[1])
        articles: list = context.user_data.get("news_articles", [])
        if not articles:
            await query.edit_message_text("Sessione scaduta. Usa /all per ricaricare.")
            return
        text = _format_news_page(articles, page)
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_build_news_keyboard(page, len(articles)),
            disable_web_page_preview=True,
        )
        return


# ---------------------------------------------------------------------------
# Daily news job
# ---------------------------------------------------------------------------

async def send_daily_news_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: send filtered digest to all registered users."""
    storage: Storage = context.application.bot_data["storage"]

    articles = await fetch_articles()
    if not articles:
        logger.info("Daily job: no articles found.")
        return

    for user_id in storage.list_users():
        prefs = storage.get_user_prefs(user_id)
        filtered = [
            art
            for art in articles[:MAX_DIGEST_ITEMS]
            if _article_matches(art, prefs)
        ]
        if not filtered:
            continue
        digest = _format_digest(filtered)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=digest,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Error sending digest to user_id=%s", user_id)


def _article_matches(art: dict, prefs: dict) -> bool:
    if not prefs["macro"] and not prefs["branches"]:
        return True
    macro, branch = classify_article(art["title"])
    macro_ok = not prefs["macro"] or macro in prefs["macro"]
    branch_ok = not prefs["branches"] or branch in prefs["branches"]
    return macro_ok and branch_ok


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception", exc_info=context.error)
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ Bot error: {context.error}",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Variabile d'ambiente BOT_TOKEN mancante. Esegui: export BOT_TOKEN='...'"
        )

    app = ApplicationBuilder().token(token).build()

    storage = Storage(os.getenv("DB_PATH", "bot.db"))
    app.bot_data["storage"] = storage

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("domains", domains))
    app.add_handler(CommandHandler("branches", branches))
    app.add_handler(CommandHandler("preferences", preferences))
    app.add_handler(CommandHandler("all", all_news))
    app.add_handler(CommandHandler("reset", reset))

    # Callback query handler
    app.add_handler(CallbackQueryHandler(button))

    # Error handler
    app.add_error_handler(error_handler)

    # Daily digest job
    app.job_queue.run_daily(
        send_daily_news_job,
        time=dtime(hour=SEND_HOUR, minute=0, second=0),
    )

    logger.info("Bot avviato. Invio digest alle %02d:00.", SEND_HOUR)
    app.run_polling()


if __name__ == "__main__":
    main()
