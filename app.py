from flask import Flask, render_template, request
import feedparser
import urllib.request
import re
import os
from datetime import datetime
import email.utils

app = Flask(__name__)

FEEDS = [
    # General
    {"source": "BBC Business", "category": "general", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "The Guardian Business", "category": "general", "url": "https://www.theguardian.com/uk/business/rss"},
    {"source": "Reuters Business", "category": "general", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"source": "AP Business", "category": "general", "url": "https://feeds.apnews.com/rss/apf-business"},
    {"source": "NPR Business", "category": "general", "url": "https://feeds.npr.org/1006/rss.xml"},
    {"source": "Business Insider", "category": "general", "url": "https://feeds.businessinsider.com/custom/all"},

    # Markets
    {"source": "MarketWatch", "category": "markets", "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"source": "Yahoo Finance", "category": "markets", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "Nasdaq News", "category": "markets", "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets"},
    {"source": "Investing.com", "category": "markets", "url": "https://www.investing.com/rss/news.rss"},
    {"source": "Barron's", "category": "markets", "url": "https://www.barrons.com/xml/rss/3_7552.xml"},

    # Economy
    {"source": "CNBC Economy", "category": "economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"source": "The Economist", "category": "economy", "url": "https://www.economist.com/finance-and-economics/rss.xml"},
    {"source": "Fortune", "category": "economy", "url": "https://fortune.com/feed/"},
    {"source": "South China Morning Post", "category": "economy", "url": "https://www.scmp.com/rss/91/feed"},

    # Tech
    {"source": "CNBC Tech", "category": "tech", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"},
    {"source": "TechCrunch", "category": "tech", "url": "https://techcrunch.com/feed/"},
    {"source": "The Verge", "category": "tech", "url": "https://www.theverge.com/rss/index.xml"},
    {"source": "Ars Technica Business", "category": "tech", "url": "https://feeds.arstechnica.com/arstechnica/business"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def parse_date(entry):
    for field in ['published', 'updated']:
        val = entry.get(field, '')
        if val:
            try:
                return email.utils.parsedate_to_datetime(val)
            except Exception:
                pass
    return datetime.min

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
        response = urllib.request.urlopen(req, timeout=8)
        content = response.read()
        parsed = feedparser.parse(content)
        articles = []
        for entry in parsed.entries[:15]:
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

@app.route("/")
def index():
    category = request.args.get("category", "all")
    date_filter = request.args.get("date", "")

    articles = []
    for feed in FEEDS:
        if category == "all" or feed["category"] == category:
            articles.extend(fetch_feed(feed))

    # Sort newest first
    articles.sort(key=lambda x: x["published_dt"], reverse=True)

    # Date filter
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            articles = [a for a in articles if a["published_dt"] != datetime.min and a["published_dt"].date() == filter_date]
        except Exception:
            pass

    return render_template("index.html", articles=articles, active_category=category, date_filter=date_filter)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)