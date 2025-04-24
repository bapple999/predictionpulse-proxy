import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GAMMA_URL = "https://gamma-api.polymarket.com/markets"

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

def fetch_polymarket():
    res = requests.get(GAMMA_URL, params={"limit": 100})
    res.raise_for_status()
    markets = res.json()

    cleaned = []

    for market in markets:
        try:
            prices = market.get("outcomePrices")
            if not prices:
                continue

            avg_price = sum(map(float, prices)) / len(prices)
            volume = float(market.get("volumeClob", 0))

            cleaned.append({
                "market_id": market.get("id"),
                "price": round(avg_price, 4),
                "volume": volume,
                "source": "polymarket",
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"⚠️ Skipping bad market: {e}")

    insert_to_supabase(cleaned)

if __name__ == "__main__":
    fetch_polymarket()
