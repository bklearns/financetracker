from flask import Flask, render_template, request
import feedparser
import urllib.request
import urllib.parse
import json
import re
import os
from datetime import datetime, timezone
import email.utils

app = Flask(__name__)

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

FEEDS = [
    {"source": "Yahoo Finance", "category": "markets", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "TechCrunch", "category": "tech", "url": "https://techcrunch.com/feed/"},
    {"source": "CNBC Economy", "category": "economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"source": "CNBC Tech", "category": "tech", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"},
    {"source": "CNBC Markets", "category": "markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"},
    {"source": "Reuters Business", "category": "general", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"source": "AP Business", "category": "general", "url": "https://feeds.apnews.com/rss/apf-business"},
    {"source": "NPR Business", "category": "general", "url": "https://feeds.npr.org/1006/rss.xml"},
    {"source": "Nasdaq News", "category": "markets", "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets"},
    {"source": "The Economist", "category": "economy", "url": "https://www.economist.com/finance-and-economics/rss.xml"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Cache for articles and Unsplash images
cache = {"articles": [], "last_updated": None}
unsplash_cache = {}

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
        url = entry.media_thumbnail[0].get('url', '')
        if url:
            return url
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            url = m.get('url', '')
            if url and any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return url
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')
    for field in ['content', 'summary']:
        text = ''
        if field == 'content' and hasattr(entry, 'content') and entry.content:
            text = entry.content[0].get('value', '')
        else:
            text = entry.get('summary', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', text)
        if img_match:
            url = img_match.group(1)
            if url.startswith('http'):
                return url
    return ''

def get_unsplash_image(keyword):
    if not UNSPLASH_KEY:
        return ''
    # Use cached result if available
    if keyword in unsplash_cache:
        return unsplash_cache[keyword]
    try:
        query = urllib.parse.quote(keyword)
        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=5&orientation=landscape&client_id={UNSPLASH_KEY}"
        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, timeout=5)
        data = json.loads(response.read())
        results = data.get('results', [])
        if results:
            img_url = results[0]['urls']['regular']
            unsplash_cache[keyword] = img_url
            return img_url
    except Exception:
        pass
    return ''

def get_fallback_keyword(title, category):
    # Pick a smart search keyword based on category
    keywords = {
        'markets': 'stock market trading',
        'economy': 'economy finance',
        'tech': 'technology business',
        'general': 'business finance',
    }
    return keywords.get(category, 'finance')

def fetch_feed(feed):
    try:
        req = urllib.request.Request(feed["url"], headers=HEADERS)
        response = urllib.request.urlopen(req, timeout=5)
        content = response.read()
        parsed = feedparser.parse(content)
        articles = []
        for entry in parsed.entries[:8]:
            dt = parse_date(entry)
            image = extract_image(entry)
            articles.append({
                "source": feed["source"],
                "category": feed["category"],
                "title": clean(entry.get("title", "No title")),
                "link": entry.get("link", "#"),
                "summary": clean(entry.get("summary", ""))[:180],
                "published": entry.get("published", ""),
                "published_dt": dt,
                "image": image,
                "has_image": bool(image),
            })
        return articles
    except Exception:
        return []

def interleave(all_articles_by_source):
    result = []
    while any(all_articles_by_source):
        for source_list in all_articles_by_source:
            if source_list:
                result.append(source_list.pop(0))
    return result

def refresh_cache():
    by_source = []
    for feed in FEEDS:
        articles = fetch_feed(feed)
        if articles:
            by_source.append(articles)

    mixed = interleave(by_source)
    mixed.sort(key=lambda x: x["published_dt"], reverse=True)

    # Fill missing images with Unsplash
    for article in mixed:
        if not article["image"]:
            keyword = get_fallback_keyword(article["title"], article["category"])
            article["image"] = get_unsplash_image(keyword)

    cache["articles"] = mixed
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