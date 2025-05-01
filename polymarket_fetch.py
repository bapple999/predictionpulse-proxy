import os
import requests
from datetime import datetime
import time

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
        if res.status_code == 429:
            print("⏳ Rate limited. Sleeping 10 seconds...")
            time.sleep(10)
            continue
        res.raise_for_status()
        batch = res.json()
        if not batch:
            break
        all_markets.extend(batch)
        print(f"🔄 Retrieved {len(batch)} markets (offset {offset})")
        offset += limit
        time.sleep(0.25)  # prevent rate limits

    print(f"📦 Total markets fetched: {len(all_markets)}")

    # Filter: future expiration
    now_iso = datetime.utcnow().isoformat()
    future_markets = [
        m for m in all_markets
        if m.get("endDate") and m["endDate"] > now_iso
    ]
    print(f"⏳ Markets with future expiration: {len(future_markets)}")

    # Sort by volume and take top 1,000
    sorted_markets = sorted(
        future_markets,
        key=lambda m: float(m.get("volumeUsd") or 0),
        reverse=True
    )
    top_markets = sorted_markets[:1000]
    print(f"🏆 Top 1000 future markets by volume selected")

    payload = []
    for market in top_markets:
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
            "volume": float(market.get("volumeUsd", 0)),
            "liquidity": float(market.get("liquidity", 0)),
            "status": market.get("status", "unknown"),
            "expiration": market.get("endDate"),
            "tags": market.get("categories", []),
            "source": "polymarket_gamma",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    print(f"🚀 Prepared {len(payload)} markets to insert")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()
