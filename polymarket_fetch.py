import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GAMMA_API = "https://gamma-api.polymarket.com/markets"

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
    response = requests.get(GAMMA_API)
    response.raise_for_status()
    markets = response.json()

    cleaned = []

    for market in markets:
        prices_raw = market.get("outcomePrices")
        try:
            prices = list(map(float, eval(prices_raw)))  # Convert from string like '["0.5", "0.5"]'
        except Exception as e:
            print(f"⚠️ Skipping bad market {market.get('id')}: {e}")
            continue

        if not prices:
            continue

        avg_price = sum(prices) / len(prices)
        cleaned.append({
            "market_id": market.get("id"),
            "price": round(avg_price, 4),
            "volume": float(market.get("volumeClob", 0)),
            "source": "polymarket",
            "timestamp": datetime.utcnow().isoformat()
        })

    insert_to_supabase(cleaned)

if __name__ == "__main__":
    fetch_polymarket()
