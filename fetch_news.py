import feedparser
import urllib.request
import urllib.parse
import json
import re
import os
from datetime import datetime, timezone
import email.utils
import random
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

CATEGORY_SEARCHES = {
    "markets": "stock market trading floor",
    "economy": "central bank federal reserve",
    "tech": "technology silicon valley",
    "general": "business finance corporate",
}

unsplash_pool = {}

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
    return datetime.now(timezone.utc)

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

def load_unsplash_pool():
    if not UNSPLASH_KEY:
        return
    for category, query in CATEGORY_SEARCHES.items():
        try:
            q = urllib.parse.quote(query)
            url = f"https://api.unsplash.com/search/photos?query={q}&per_page=10&orientation=landscape&client_id={UNSPLASH_KEY}"
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read())
            results = data.get('results', [])
            unsplash_pool[category] = [r['urls']['regular'] for r in results]
        except Exception:
            unsplash_pool[category] = []

def get_pooled_image(category):
    pool = unsplash_pool.get(category, [])
    return random.choice(pool) if pool else ''

def fetch_and_store():
    load_unsplash_pool()
    articles = []
    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers=HEADERS)
            response = urllib.request.urlopen(req, timeout=5)
            content = response.read()
            parsed = feedparser.parse(content)
            for entry in parsed.entries[:8]:
                dt = parse_date(entry)
                image = extract_image(entry)
                if not image:
                    image = get_pooled_image(feed["category"])
                articles.append({
                    "source": feed["source"],
                    "category": feed["category"],
                    "title": clean(entry.get("title", "No title")),
                    "link": entry.get("link", "#"),
                    "summary": clean(entry.get("summary", ""))[:180],
                    "published": entry.get("published", ""),
                    "published_dt": dt.isoformat(),
                    "image": image,
                })
        except Exception as e:
            print(f"Error fetching {feed['source']}: {e}")

    # Upsert articles into Supabase (link is unique so duplicates are ignored)
    if articles:
        supabase.table("articles").upsert(articles, on_conflict="link").execute()
        print(f"Stored {len(articles)} articles")

if __name__ == "__main__":
    fetch_and_store()