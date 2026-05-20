from flask import Flask, render_template
import feedparser
import urllib.request
import re
import os

app = Flask(__name__)

FEEDS = [
    {"source": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "The Guardian Business", "url": "https://www.theguardian.com/uk/business/rss"},
    {"source": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"source": "CNBC", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"},
    {"source": "Reuters", "url": "https://feeds.reuters.com/reuters/businessNews"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def clean(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        response = urllib.request.urlopen(req, timeout=10)
        content = response.read()
        return feedparser.parse(content)
    except Exception:
        return feedparser.parse("")

@app.route("/")
def index():
    articles = []
    for feed in FEEDS:
        parsed = fetch_feed(feed["url"])
        for entry in parsed.entries[:5]:
            articles.append({
                "source": feed["source"],
                "title": clean(entry.get("title", "No title")),
                "link": entry.get("link", "#"),
                "summary": clean(entry.get("summary", ""))[:200],
                "published": entry.get("published", ""),
            })
    return render_template("index.html", articles=articles)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)