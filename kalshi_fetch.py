import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2/markets"
headers = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"
}

def insert_to_supabase(payload):
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/market_snapshots",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        json=payload
    )
    print(f"✅ Supabase insert status: {res.status_code}")
    if res.status_code != 201:
        print("⚠️", res.text)

def fetch_kalshi():
    res = requests.get(KALSHI_API, headers=headers)
    res.raise_for_status()
    markets = res.json().get("markets", [])

    cleaned = []

    for market in markets:
        yes_bid = market.get("yes_bid")
        no_bid = market.get("no_bid")
        if yes_bid is None or no_bid is None:
            continue
        prob = (yes_bid + (1 - no_bid)) / 2

        cleaned.append({
            "market_id": market.get("ticker"),
            "price": round(prob, 4),
            "volume": market.get("volume", 0),
            "source": "kalshi",
            "timestamp": datetime.utcnow().isoformat()
        })

    insert_to_supabase(cleaned)

if __name__ == "__main__":
    fetch_kalshi()
