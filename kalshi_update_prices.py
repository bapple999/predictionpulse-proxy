import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
KALSHI_API = "https://trading-api.kalshi.com/trade-api/v2/markets"

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

def fetch_kalshi_market_updates():
    print("📡 Fetching Kalshi market prices...")
    res = requests.get(KALSHI_API)
    res.raise_for_status()
    data = res.json()

    timestamp = datetime.utcnow().isoformat() + "Z"
    snapshots = []
    outcomes = []

    for m in data.get("markets", []):
        market_id = m.get("ticker")
        if not market_id:
            continue

        yes_price = m.get("last_yes_price")
        no_price = m.get("last_no_price")

        if yes_price is None or no_price is None:
            continue

        snapshots.append({
            "market_id": market_id,
            "price": float(yes_price),
            "volume": float(m.get("volume", 0)),
            "liquidity": float(m.get("liquidity", 0)),
            "status": m.get("status", "active"),
            "timestamp": timestamp,
            "source": "kalshi"
        })

        outcomes.append({
            "market_id": market_id,
            "outcome_name": "Yes",
            "price": float(yes_price),
            "volume": float(m.get("volume", 0)),
            "timestamp": timestamp,
            "source": "kalshi"
        })

        outcomes.append({
            "market_id": market_id,
            "outcome_name": "No",
            "price": float(no_price),
            "volume": float(m.get("volume", 0)),
            "timestamp": timestamp,
            "source": "kalshi"
        })

    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_kalshi_market_updates()
