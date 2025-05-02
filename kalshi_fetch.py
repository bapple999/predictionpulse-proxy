import os
import requests
from datetime import datetime
import time

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
KALSHI_MARKETS_API = "https://api.elections.kalshi.com/trade-api/v2/markets"
KALSHI_EVENTS_API = "https://api.elections.kalshi.com/trade-api/v2/events"
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

def fetch_events():
    print("📡 Fetching Kalshi events...")
    res = requests.get(KALSHI_EVENTS_API, headers=HEADERS)
    res.raise_for_status()
    events = res.json().get("events", [])
    return {e["ticker"]: e for e in events if "ticker" in e}

def fetch_all_markets():
    print("📡 Fetching all Kalshi markets with pagination...")
    all_markets = []
    offset = 0
    limit = 100

    while True:
        res = requests.get(KALSHI_MARKETS_API, headers=HEADERS, params={"limit": limit, "offset": offset})
        res.raise_for_status()
        batch = res.json().get("markets", [])
        if not batch:
            break
        all_markets.extend(batch)
        print(f"🔄 Retrieved {len(batch)} markets (offset {offset})")
        offset += limit
        time.sleep(0.1)

    print(f"📦 Total markets fetched: {len(all_markets)}")
    return all_markets

def fetch_kalshi():
    all_markets = fetch_all_markets()
    events = fetch_events()
    now = datetime.utcnow().isoformat()

    valid_markets = []
    for market in all_markets:
        try:
            if not market.get("expiration") or market["expiration"] <= now:
                continue
            if float(market.get("volume", 0)) <= 0:
                continue
            valid_markets.append(market)
        except Exception:
            continue

    print(f"✅ Valid markets after filters: {len(valid_markets)}")
    sorted_markets = sorted(valid_markets, key=lambda m: float(m.get("volume", 0)), reverse=True)
    top_markets = sorted_markets[:1000]

    timestamp = datetime.utcnow().isoformat() + "Z"
    markets_data = []
    snapshots = []
    outcomes = []

    for m in top_markets:
        market_id = m.get("ticker")
        event = events.get(m.get("event_ticker"), {})
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        prob = (yes_bid + (1 - no_bid)) / 2 if yes_bid is not None and no_bid is not None else None

        markets_data.append({
            "market_id": market_id,
            "market_name": m.get("title"),
            "market_description": m.get("description"),
            "event_name": event.get("title") if event else None,
            "event_ticker": m.get("event_ticker"),
            "expiration": m.get("expiration"),
            "tags": m.get("tags", []),
            "source": "kalshi",
            "status": m.get("status")
        })

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

    insert_to_supabase("markets", markets_data)
    insert_to_supabase("market_snapshots", snapshots)
    insert_to_supabase("market_outcomes", outcomes)

if __name__ == "__main__":
    fetch_kalshi()
