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
    print("📡 Fetching Polymarket markets from Gamma API...")
    limit = 100
    offset = 0
    all_markets = []

    while True:
        res = requests.get(GAMMA_API, params={"limit": limit, "offset": offset})
        res.raise_for_status()
        batch = res.json()
        if not batch:
            break
        all_markets.extend(batch)
        print(f"🔄 Retrieved {len(batch)} markets (offset {offset})")
        offset += limit

    print(f"🔍 Total markets retrieved: {len(all_markets)}")

    payload = []

    for market in all_markets:
        try:
            prices = list(map(float, eval(market.get("outcomePrices", "[]"))))
            if not prices:
                continue
            avg_price = sum(prices) / len(prices)
        except Exception as e:
            print(f"⚠️ Skipping market {market.get('id')} due to price error: {e}")
            continue

        payload.append({
            "market_id": market.get("id"),
            "market_name": market.get("title", ""),
            "market_description": market.get("description", None),
            "event_name": "Polymarket",
            "event_ticker": None,
            "price": round(avg_price, 4),
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volumeUsd", 0)),  # USD volume
            "liquidity": float(market.get("liquidity", 0)),
            "status": market.get("status", "unknown"),
            "expiration": market.get("endDate"),
            "tags": market.get("categories", []),
            "source": "polymarket_gamma",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    print(f"📦 Prepared {len(payload)} entries for Supabase")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()
