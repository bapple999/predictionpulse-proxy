import os
import requests
from datetime import datetime
import time

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GAMMA_API = "https://gamma-api.polymarket.com/markets"
CLOB_API_BASE = "https://clob.polymarket.com/markets"

def insert_to_supabase(endpoint, payload):
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/{endpoint}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        json=payload
    )
    print(f"✅ Supabase insert to {endpoint} status: {res.status_code}")
    if res.status_code != 201:
        print("⚠️", res.text)

def fetch_polymarket():
    print("📡 Fetching Polymarket markets from Gamma API with pagination...")
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
        time.sleep(0.1)

    print(f"📦 Total markets fetched: {len(all_markets)}")

    now = datetime.utcnow().isoformat()
    valid_markets = []
    for m in all_markets:
        try:
            if not m.get("endDate") or m["endDate"] <= now:
                continue
            if float(m.get("volumeUsd") or 0) < 1:
                continue
            prices = list(map(float, eval(m.get("outcomePrices", "[]"))))
            if not prices:
                continue
        except Exception as e:
            continue
        valid_markets.append(m)

    print(f"✅ Valid markets after filters: {len(valid_markets)}")

    sorted_markets = sorted(valid_markets, key=lambda m: float(m.get("volumeUsd") or 0), reverse=True)
    top_markets = sorted_markets[:1000]

    snapshots = []
    outcomes = []

    for market in top_markets:
        market_id = market.get("id")
        timestamp = datetime.utcnow().isoformat() + "Z"

        try:
            clob_res = requests.get(f"{CLOB_API_BASE}/{market_id}")
            clob_res.raise_for_status()
            clob_data = clob_res.json()
            outcome_data = clob_data.get("outcomes", [])
        except Exception as e:
            print(f"⚠️ Failed to fetch CLOB data for {market_id}: {e}")
            outcome_data = []

        price_list = [float(o.get("price", 0.5)) for o in outcome_data if o.get("price") is not None]
        avg_price = round(sum(price_list) / len(price_list), 4) if price_list else 0.5

        snapshots.append({
            "market_id": market_id,
            "market_name": market.get("title") or market.get("slug", ""),
            "market_description": market.get("description", None),
            "event_name": market.get("title") or "Polymarket",
            "event_ticker": None,
            "price": avg_price,
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volumeUsd", 0)),
            "liquidity": float(market.get("liquidity", 0)),
            "status": "active",
            "expiration": market.get("endDate"),
            "tags": market.get("categories", ["polymarket"]),
            "source": "polymarket_gamma+clob",
            "timestamp": timestamp
        })

        for o in outcome_data:
            if "name" not in o or "price" not in o:
                continue
            outcomes.append({
                "market_id": market_id,
                "outcome_name": o["name"],
                "price": float(o["price"]),
                "volume": float(o.get("volume", 0)),
                "timestamp": timestamp,
                "source": "polymarket_clob"
            })

    print(f"🚀 Prepared {len(snapshots)} snapshot entries and {len(outcomes)} outcome entries")
    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_polymarket()
