import os
import requests
from datetime import datetime
import time

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
KALSHI_MARKETS_API = "https://api.elections.kalshi.com/trade-api/v2/markets"
HEADERS = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"
}

def insert_to_supabase(endpoint, payload):
    if not payload:
        print(f"⚠️ No payload to insert for {endpoint}")
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
    print(f"✅ Supabase insert to {endpoint} status: {res.status_code}")
    if res.status_code != 201:
        print("⚠️", res.text)

def fetch_kalshi_price_updates():
    print("📡 Fetching Kalshi market price updates...")
    res = requests.get(KALSHI_MARKETS_API, headers=HEADERS)
    res.raise_for_status()
    all_markets = res.json().get("markets", [])

    timestamp = datetime.utcnow().isoformat() + "Z"
    snapshots = []
    outcomes = []

    for m in all_markets:
        market_id = m.get("ticker")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        prob = (yes_bid + (1 - no_bid)) / 2 if yes_bid is not None and no_bid is not None else None

        snapshots.append({
            "market_id": market_id,
            "price": round(prob, 4) if prob is not None else None,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": m.get("volume"),
            "liquidity": m.get("open_interest"),
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

    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_kalshi_price_updates()
