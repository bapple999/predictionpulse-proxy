import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

POLYMARKET_API = "https://strapi-matic.poly.market/markets"

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
    print("📡 Fetching Polymarket markets from REST API...")
    all_markets = []
    page = 0
    per_page = 100

    while True:
        params = {
            "_limit": per_page,
            "_start": page * per_page
        }
        res = requests.get(POLYMARKET_API, params=params)
        res.raise_for_status()
        markets = res.json()

        if not markets:
            break

        all_markets.extend(markets)
        print(f"🔄 Page {page + 1}: Retrieved {len(markets)} markets")
        page += 1

    print(f"🔍 Total markets retrieved: {len(all_markets)}")

    payload = []
    for market in all_markets:
        outcomes = market.get("outcomes", [])
        try:
            prices = [float(outcome.get("price", 0)) for outcome in outcomes if outcome.get("price") is not None]
            prob = round(prices[0], 4) if prices else None
        except Exception as e:
            print(f"⚠️ Skipping market {market.get('id')} due to price error: {e}")
            continue

        payload.append({
            "market_id": market.get("id", ""),
            "market_name": market.get("title", ""),
            "market_description": market.get("description", None),
            "event_name": "Polymarket",
            "event_ticker": None,
            "price": prob,
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volume", 0)),
            "liquidity": float(market.get("liquidity", 0)),
            "status": market.get("status", "unknown"),
            "expiration": market.get("end_date", None),
            "tags": market.get("tags", []),
            "source": "polymarket_rest",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    print(f"📦 Prepared {len(payload)} entries for Supabase")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()
