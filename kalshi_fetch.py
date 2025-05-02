import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
KALSHI_MARKETS_API = "https://trading-api.kalshi.com/trade-api/v2/markets"
KALSHI_EVENTS_API = "https://trading-api.kalshi.com/trade-api/v2/events"

def insert_to_supabase(endpoint, payload):
    if not payload:
        print(f"⚠️ No data to insert for {endpoint}")
        return
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
    print(f"✅ Inserted {len(payload)} records to {endpoint} - Status: {res.status_code}")
    if res.status_code != 201:
        print("⚠️ Error:", res.text)

def fetch_kalshi():
    print("📡 Fetching Kalshi markets...")
    res = requests.get(KALSHI_MARKETS_API)
    res.raise_for_status()
    markets = res.json().get("markets", [])
    print(f"🔍 Retrieved {len(markets)} markets")

    print("📡 Fetching Kalshi events...")
    events_res = requests.get(KALSHI_EVENTS_API)
    events_res.raise_for_status()
    events = {e["ticker"]: e for e in events_res.json().get("events", [])}
    print(f"📂 Loaded {len(events)} events")

    now = datetime.utcnow().isoformat()
    filtered = [
        m for m in markets
        if m.get("expiration") and m["expiration"] > now and m.get("volume", 0) > 0
    ]
    sorted_markets = sorted(filtered, key=lambda m: m.get("volume", 0), reverse=True)
    top_markets = sorted_markets[:1000]

    markets_data, snapshots, outcomes = [], [], []
    timestamp = datetime.utcnow().isoformat() + "Z"

    for m in top_markets:
        market_id = m.get("ticker")
        event = events.get(m.get("event_ticker"), {})
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        prob = (yes_bid + (1 - no_bid)) / 2 if yes_bid is not None and no_bid is not None else None

        markets_data.append({
            "market_id": market_id,
            "market_name": m.get("title"),
            "description": m.get("description"),
            "tags": m.get("tags", []),
            "expiration": m.get("expiration"),
            "source": "kalshi"
        })

        snapshots.append({
            "market_id": market_id,
            "price": round(prob, 4) if prob is not None else None,
            "volume": m.get("volume"),
            "liquidity": m.get("open_interest"),
            "status": m.get("status"),
            "timestamp": timestamp,
            "source": "kalshi"
        })

        if yes_bid is not None:
            outcomes.append({
                "market_id": market_id,
                "outcome_name": "Yes",
                "price": yes_bid,
                "volume": None,
                "timestamp": timestamp,
                "source": "kalshi"
            })
        if no_bid is not None:
            outcomes.append({
                "market_id": market_id,
                "outcome_name": "No",
                "price": 1 - no_bid,
                "volume": None,
                "timestamp": timestamp,
                "source": "kalshi"
            })

    insert_to_supabase("markets", markets_data)
    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_kalshi()
