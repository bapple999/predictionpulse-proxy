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
        time.sleep(0.25)  # reduce API strain

    print(f"📦 Total markets fetched: {len(all_markets)}")

    # Filter: future expiration, volume > 1000, outcome prices not flat 0.5s
    now = datetime.utcnow().isoformat()
    valid_markets = []
    for m in all_markets:
        try:
            if not m.get("endDate") or m["endDate"] <= now:
                continue
            if float(m.get("volumeUsd") or 0) < 1000:
                continue
            prices = list(map(float, eval(m.get("outcomePrices", "[]"))))
            if all(round(p, 2) == 0.5 for p in prices):
                continue
        except Exception as e:
            continue
        valid_markets.append(m)

    print(f"✅ Valid markets after filters: {len(valid_markets)}")

    # Sort by volume
    sorted_markets = sorted(valid_markets, key=lambda m: float(m.get("volumeUsd") or 0), reverse=True)
    top_markets = sorted_markets[:1000]

    payload = []
    for market in top_markets:
        try:
            prices = list(map(float, eval(market.get("outcomePrices", "[]"))))
            if not prices:
                continue
            avg_price = sum(prices) / len(prices)
        except Exception as e:
            continue

        payload.append({
            "market_id": market.get("id"),
            "market_name": market.get("title") or market.get("slug", ""),
            "market_description": None,
            "event_name": "Polymarket",
            "event_ticker": None,
            "price": round(avg_price, 4),
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volumeUsd", 0)),
            "liquidity": float(market.get("liquidity", 0)),
            "status": "active",  # Gamma has no status field
            "expiration": market.get("endDate"),
            "tags": market.get("categories", ["polymarket"]),
            "source": "polymarket_gamma",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    print(f"🚀 Prepared {len(payload)} entries for Supabase insert")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()
