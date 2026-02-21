# Bot_TG

A Telegram bot that delivers daily filtered news digests across engineering, finance, and politics domains.

## Features

- 🌐 **Domain/branch filtering** – select macrodomains and branches of interest via interactive menus
- 📰 **Daily digest** – one consolidated message per user every morning (respects preferences)
- 🔍 **Smart classification** – sentence-transformer embeddings (default) + comprehensive keyword fallback
- 📑 **Paginated news** – `/all` shows 5 articles per page with Prev/Next buttons
- 💾 **Persistent preferences** – stored in SQLite, survive restarts
- ⚠️ **Admin notifications** – optional critical-error alerts to an admin chat
- 🛡️ **Rate limiting** – prevents abuse of commands and callbacks

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `SEND_HOUR` | ❌ | `9` | Hour (0-23) to send the daily digest |
| `MAX_DIGEST_ITEMS` | ❌ | `20` | Max articles in the daily digest |
| `USE_EMBEDDINGS` | ❌ | `1` | Set to `0` to disable sentence-transformer classification |
| `ADMIN_CHAT_ID` | ❌ | — | Chat ID to receive critical error notifications |
| `DB_PATH` | ❌ | `bot.db` | Path to the SQLite database file |

## Running

```bash
export BOT_TOKEN="your_token_here"
python main.py
```

Or copy `.env.example` to `.env` and fill in the values, then:

```bash
set -a; source .env; set +a
python main.py
```

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + interactive main menu |
| `/menu` | Show the main menu |
| `/domains` | Select macrodomains of interest |
| `/branches` | Select specific branches of interest |
| `/preferences` | Show current saved preferences |
| `/all` | Fetch and show latest news (paginated, 5 per page) |
| `/reset` | Reset all preferences to defaults |

## Interactive Menu Buttons

- **🌐 Macrodomini** – open macro selector (with ✔ Tutti / ✖ Nessuno / 🔄 Reset / ✅ Fine)
- **🔀 Rami** – open branch selector (same controls)
- **📋 Preferenze** – show current preferences inline
- **📰 News Ora** – fetch latest news immediately (paginated)
- **🔄 Reset preferenze** – clear all preferences

## Domains & Branches

| Macrodomain | Branches |
|---|---|
| Ingegneria | Elettronica, Meccanica, Biotecnologie, Nanoelettronica, Automazione |
| Finanza | Mercati, Investimenti, Criptovalute |
| Politica | Internazionale, Locale, Europea |

## Architecture

```
main.py          – bot handlers, JobQueue scheduling, pagination, error handler
news_fetcher.py  – non-blocking threaded RSS fetch with timeouts
classifier.py    – embeddings + keyword article classifier
storage.py       – SQLite-backed user preference persistence
rate_limit.py    – per-user sliding-window rate limiter
```

## Troubleshooting

**Bot doesn't start**
- Ensure `BOT_TOKEN` is set: `echo $BOT_TOKEN`
- Check Python version ≥ 3.10

**Embeddings slow to load**
- First run downloads `all-MiniLM-L6-v2` (~80 MB). Subsequent runs use the cache.
- Disable with `USE_EMBEDDINGS=0` if you want keyword-only classification.

**No news articles**
- RSS feeds may be temporarily unavailable. The fetcher times out after ~12 seconds and continues.
- Check network connectivity.

**Preferences not saved**
- Ensure write permission in the working directory for `bot.db` (or set `DB_PATH`).
