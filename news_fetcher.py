import feedparser
from newspaper import Article

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.technologyreview.com/feed/"
]

async def fetch_articles():
    articles = []
    for feed in RSS_FEEDS:
        d = feedparser.parse(feed)
        for entry in d.entries[:5]:
            art = Article(entry.link)
            art.download()
            art.parse()
            articles.append({"title": art.title, "url": entry.link})
    return articles
