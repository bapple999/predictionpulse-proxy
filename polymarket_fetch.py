import os
import requests
from datetime import datetime
import time

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GAMMA_API = "https://gamma-api.polymarket.com/markets"
CLOB_API_BASE = "https://clob.polymarket.com/markets"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def insert_to_supabase(endpoint, payload):
    if not payload:
        print(f"⚠️ No data to insert into {endpoint}")
        return
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/{endpoint}",
        headers=HEADERS,
        json=payload
    )
    print(f"✅ Inserted into {endpoint} | Status: {res.status_code}")
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
    filtered = [
        m for m in all_markets
        if m.get("endDate") and m.get("endDate") > now and float(m.get("volumeUsd") or 0) > 0
    ]
    sorted_markets = sorted(filtered, key=lambda m: float(m.get("volumeUsd", 0)), reverse=True)
    top_markets = sorted_markets[:1000]

    markets, snapshots, outcomes = [], [], []
    timestamp = datetime.utcnow().isoformat() + "Z"

    for m in top_markets:
        market_id = m["id"]

        # Markets metadata table
        markets.append({
            "market_id": market_id,
            "market_name": m.get("title") or m.get("slug", ""),
            "description": m.get("description"),
            "tags": m.get("categories", []),
            "expiration": m.get("endDate"),
            "source": "polymarket",
        })

        # Real-time snapshot
        try:
            clob_res = requests.get(f"{CLOB_API_BASE}/{market_id}")
            clob_res.raise_for_status()
            clob_data = clob_res.json()
            clob_outcomes = clob_data.get("outcomes", [])
        except Exception as e:
            print(f"⚠️ CLOB error for {market_id}: {e}")
            clob_outcomes = []

        prices = [float(o["price"]) for o in clob_outcomes if o.get("price") is not None]
        avg_price = round(sum(prices) / len(prices), 4) if prices else 0.5

        snapshots.append({
            "market_id": market_id,
            "price": avg_price,
            "volume": float(m.get("volumeUsd", 0)),
            "liquidity": float(m.get("liquidity", 0)),
            "status": "active",
            "timestamp": timestamp,
            "source": "polymarket_clob"
        })

        for o in clob_outcomes:
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

    insert_to_supabase("markets", markets)
    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_polymarket()
