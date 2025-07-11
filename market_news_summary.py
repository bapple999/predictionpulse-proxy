import os
import requests
import feedparser
from datetime import datetime, timedelta
import openai

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_KEY   = os.environ.get("OPENAI_API_KEY")

SUPA_HEADERS = {
    "apikey":        SERVICE_KEY or "",
    "Authorization": f"Bearer {SERVICE_KEY}" if SERVICE_KEY else "",
    "Content-Type":  "application/json",
}

openai.api_key = OPENAI_KEY

NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

def fetch_latest_price(mid: str):
    url = f"{SUPABASE_URL}/rest/v1/latest_snapshots?select=price,volume,market_name&market_id=eq.{mid}"
    r = requests.get(url, headers=SUPA_HEADERS, timeout=10)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None

def fetch_price_24h_ago(mid: str):
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
    url = (
        f"{SUPABASE_URL}/rest/v1/market_snapshots?select=price&market_id=eq.{mid}&timestamp=lt.{since}&order=timestamp.desc&limit=1"
    )
    r = requests.get(url, headers=SUPA_HEADERS, timeout=10)
    r.raise_for_status()
    rows = r.json()
    return rows[0]["price"] if rows else None

def fetch_google_news(query: str, limit: int = 3):
    url = NEWS_RSS.format(query=requests.utils.quote(query))
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    return [(e.title, e.link) for e in feed.entries[:limit]]

def summarize_articles(market: str, articles):
    if not OPENAI_KEY:
        return "(OpenAI key missing – cannot summarize)"
    headlines = "\n".join(f"- {t}" for t, _ in articles)
    prompt = (
        f"Recent news about {market}:\n{headlines}\n\n"
        "Write a short, punchy tweet-style summary, then give a brief outlook on future developments."
    )
    try:
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return res.choices[0].message["content"].strip()
    except Exception as e:
        return f"(AI summary failed: {e})"

def detect_movers(change_pct: float = 5.0, volume_threshold: int = 10000):
    url = f"{SUPABASE_URL}/rest/v1/latest_snapshots?select=market_id&limit=200"
    r = requests.get(url, headers=SUPA_HEADERS, timeout=10)
    r.raise_for_status()
    ids = [row["market_id"] for row in r.json()]

    movers = []
    for mid in ids:
        cur = fetch_latest_price(mid)
        if not cur:
            continue
        prev_price = fetch_price_24h_ago(mid)
        if prev_price is None or cur["price"] is None:
            continue
        change = (cur["price"] - prev_price) * 100
        if abs(change) >= change_pct and (cur["volume"] or 0) >= volume_threshold:
            movers.append({
                "market_id": mid,
                "market_name": cur.get("market_name") or mid,
                "change_pct": round(change, 2),
            })
    return movers

def main():
    movers = detect_movers()
    if not movers:
        print("No big movers found.")
        return
    for m in movers:
        print(f"\n== {m['market_name']} ({m['change_pct']}% change) ==")
        articles = fetch_google_news(m["market_name"])
        for t, link in articles:
            print(f"- {t}\n  {link}")
        summary = summarize_articles(m["market_name"], articles)
        print("Summary:\n", summary)

if __name__ == "__main__":
    main()

