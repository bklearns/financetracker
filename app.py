from flask import Flask, render_template, request
import feedparser
import urllib.request
import re
import os

app = Flask(__name__)

FEEDS = [
    # General
    {"source": "BBC Business", "category": "general", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "The Guardian Business", "category": "general", "url": "https://www.theguardian.com/uk/business/rss"},
    {"source": "Reuters Business", "category": "general", "url": "https://feeds.reuters.com/reuters/businessNews"},

    # Markets
    {"source": "MarketWatch", "category": "markets", "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"source": "Yahoo Finance", "category": "markets", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "Investing.com", "category": "markets", "url": "https://www.investing.com/rss/news.rss"},

    # Economy
    {"source": "CNBC Economy", "category": "economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"source": "FT Economy", "category": "economy", "url": "https://www.ft.com/rss/home/uk"},
    {"source": "The Economist", "category": "economy", "url": "https://www.economist.com/finance-and-economics/rss.xml"},

    # Tech
    {"source": "CNBC Tech", "category": "tech", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"},
    {"source": "TechCrunch", "category": "tech", "url": "https://techcrunch.com/feed/"},
    {"source": "The Verge", "category": "tech", "url": "https://www.theverge.com/rss/index.xml"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def extract_image(entry):
    # Try media_thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    # Try media_content
    if hasattr(entry, 'media_content') and entry.media_content:
        url = entry.media_content[0].get('url', '')
        if url and any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return url
    # Try enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')
    # Try parsing img from summary
    summary_html = entry.get('summary', '')
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_html)
    if img_match:
        return img_match.group(1)
    return ''

def fetch_feed(feed):
    try:
        req = urllib.request.Request(feed["url"], headers=HEADERS)
        response = urllib.request.urlopen(req, timeout=8)
        content = response.read()
        parsed = feedparser.parse(content)
        articles = []
        for entry in parsed.entries[:5]:
            articles.append({
                "source": feed["source"],
                "category": feed["category"],
                "title": clean(entry.get("title", "No title")),
                "link": entry.get("link", "#"),
                "summary": clean(entry.get("summary", ""))[:180],
                "published": entry.get("published", ""),
                "image": extract_image(entry),
            })
        return articles
    except Exception:
        return []

@app.route("/")
def index():
    category = request.args.get("category", "all")
    articles = []
    for feed in FEEDS:
        if category == "all" or feed["category"] == category:
            articles.extend(fetch_feed(feed))
    return render_template("index.html", articles=articles, active_category=category)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)