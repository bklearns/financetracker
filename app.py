from flask import Flask, render_template, request
import feedparser
import urllib.request
import re
import os
from datetime import datetime, timezone
import email.utils

app = Flask(__name__)

FEEDS = [
    {"source": "Reuters Business", "category": "general", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"source": "AP Business", "category": "general", "url": "https://feeds.apnews.com/rss/apf-business"},
    {"source": "NPR Business", "category": "general", "url": "https://feeds.npr.org/1006/rss.xml"},
    {"source": "MarketWatch Markets", "category": "markets", "url": "https://feeds.marketwatch.com/marketwatch/marketpulse/"},
    {"source": "Yahoo Finance", "category": "markets", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "Nasdaq News", "category": "markets", "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets"},
    {"source": "Investopedia", "category": "markets", "url": "https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline"},
    {"source": "CNBC Economy", "category": "economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"source": "The Economist", "category": "economy", "url": "https://www.economist.com/finance-and-economics/rss.xml"},
    {"source": "CNBC Tech", "category": "tech", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"},
    {"source": "TechCrunch", "category": "tech", "url": "https://techcrunch.com/feed/"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

cache = {"articles": [], "last_updated": None}

def clean(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def parse_date(entry):
    for field in ['published', 'updated']:
        val = entry.get(field, '')
        if val:
            try:
                dt = email.utils.parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return datetime.min.replace(tzinfo=timezone.utc)

def extract_image(entry):
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        url = entry.media_content[0].get('url', '')
        if url and any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return url
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')
    summary_html = entry.get('summary', '')
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_html)
    if img_match:
        return img_match.group(1)
    return ''

def fetch_feed(feed):
    try:
        req = urllib.request.Request(feed["url"], headers=HEADERS)
        response = urllib.request.urlopen(req, timeout=5)
        content = response.read()
        parsed = feedparser.parse(content)
        articles = []
        for entry in parsed.entries[:8]:
            dt = parse_date(entry)
            articles.append({
                "source": feed["source"],
                "category": feed["category"],
                "title": clean(entry.get("title", "No title")),
                "link": entry.get("link", "#"),
                "summary": clean(entry.get("summary", ""))[:180],
                "published": entry.get("published", ""),
                "published_dt": dt,
                "image": extract_image(entry),
            })
        return articles
    except Exception:
        return []

def refresh_cache():
    articles = []
    for feed in FEEDS:
        articles.extend(fetch_feed(feed))
    articles.sort(key=lambda x: x["published_dt"], reverse=True)
    cache["articles"] = articles
    cache["last_updated"] = datetime.now(timezone.utc)

@app.route("/")
def index():
    category = request.args.get("category", "all")
    date_filter = request.args.get("date", "")

    if not cache["articles"] or (
        cache["last_updated"] and
        (datetime.now(timezone.utc) - cache["last_updated"]).seconds > 900
    ):
        refresh_cache()

    articles = cache["articles"]

    if category != "all":
        articles = [a for a in articles if a["category"] == category]

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            articles = [a for a in articles if a["published_dt"].date() == filter_date]
        except Exception:
            pass

    return render_template("index.html", articles=articles, active_category=category, date_filter=date_filter)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)