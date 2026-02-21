import asyncio
import concurrent.futures
import logging
from typing import Dict, List

import feedparser

logger = logging.getLogger(__name__)

RSS_FEEDS: List[str] = [
    "https://techcrunch.com/feed/",
    "https://www.technologyreview.com/feed/",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

FEED_TIMEOUT: int = 10        # seconds per feed
WAIT_TIMEOUT_BUFFER: int = 2  # extra seconds for the executor.wait() deadline
MAX_ARTICLES_PER_FEED: int = 10


def _fetch_feed_sync(feed_url: str) -> List[Dict]:
    """Blocking RSS fetch – run inside a thread pool."""
    articles: List[Dict] = []
    try:
        d = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": "Mozilla/5.0"},
        )
        if d.bozo and not d.entries:
            logger.warning("Feed parse error (%s): %s", feed_url, d.bozo_exception)
            return articles
        for entry in d.entries[:MAX_ARTICLES_PER_FEED]:
            try:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                if title and link:
                    articles.append({"title": title, "url": link})
            except Exception as exc:
                logger.debug("Entry parse error in %s: %s", feed_url, exc)
    except Exception as exc:
        logger.warning("Failed to fetch feed %s: %s", feed_url, exc)
    return articles


async def fetch_articles() -> List[Dict]:
    """Fetch articles from all RSS feeds concurrently (non-blocking)."""
    loop = asyncio.get_event_loop()
    all_articles: List[Dict] = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(RSS_FEEDS), thread_name_prefix="rss"
    ) as executor:
        futures: Dict[concurrent.futures.Future, str] = {
            executor.submit(_fetch_feed_sync, feed): feed for feed in RSS_FEEDS
        }
        done, pending = concurrent.futures.wait(
            futures.keys(), timeout=FEED_TIMEOUT + WAIT_TIMEOUT_BUFFER
        )
        for future in done:
            try:
                all_articles.extend(future.result(timeout=1))
            except Exception as exc:
                logger.warning("Feed result error: %s", exc)
        for future in pending:
            logger.warning("Feed timed out: %s", futures[future])
            future.cancel()

    # Deduplicate by URL (preserve order)
    seen: set = set()
    unique: List[Dict] = []
    for art in all_articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            unique.append(art)

    logger.info("Fetched %d unique articles from %d feeds", len(unique), len(RSS_FEEDS))
    return unique
