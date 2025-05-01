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
    print("📡 Fetching Polymarket markets...")
    response = requests.get(GAMMA_API)
    response.raise_for_status()
    markets = response.json()
    print(f"🔍 Retrieved {len(markets)} markets")

    payload = []

    for market in markets:
        try:
            prices_raw = market.get("outcomePrices")
            prices = list(map(float, eval(prices_raw)))  # Convert from string like '["0.5", "0.5"]'
        except Exception as e:
            print(f"⚠️ Skipping market {market.get('id')}: {e}")
            continue

        if not prices:
            continue

        avg_price = sum(prices) / len(prices)

        payload.append({
            "market_id": market.get("id"),
            "market_name": market.get("title", ""),
            "market_description": market.get("description", ""),
            "event_name": market.get("category", ""),  # not a true event, but serves that role
            "event_ticker": None,  # Polymarket doesn’t use this
            "price": round(avg_price, 4),
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volumeClob", 0)),
            "liquidity": float(market.get("liquidity", 0)),
            "status": market.get("status"),
            "expiration": market.get("endDate"),
            "tags": [market.get("category")] if market.get("category") else [],
            "source": "polymarket",
            "timestamp": datetime.utcnow().isoformat()
        })

    print(f"📦 Prepared {len(payload)} market entries for Supabase")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()

