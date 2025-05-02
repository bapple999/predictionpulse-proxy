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

def fetch_events():
    print("📡 Fetching Kalshi events...")
    res = requests.get(KALSHI_EVENTS_API, headers=HEADERS)
    res.raise_for_status()
    events = res.json().get("events", [])

    event_dict = {}
    for event in events:
        ticker = event.get("ticker") or event.get("event_ticker")
        if ticker:
            event_dict[ticker] = event
    print(f"📂 Loaded {len(event_dict)} valid events")
    return event_dict

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

    payload = []
    for market in top_markets:
        yes_bid = market.get("yes_bid")
        no_bid = market.get("no_bid")
        if yes_bid is None or no_bid is None:
            price = 0.5
        else:
            price = (yes_bid + (1 - no_bid)) / 2

        event_ticker = market.get("event_ticker", "")
        event = events.get(event_ticker, {})
        event_name = event.get("title", "") if event else ""

        payload.append({
            "market_id": market.get("ticker", ""),
            "market_name": market.get("title", ""),
            "market_description": market.get("description", ""),
            "event_name": event_name,
            "event_ticker": event_ticker,
            "price": round(price, 4),
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": market.get("volume", 0),
            "liquidity": market.get("open_interest", 0),
            "status": market.get("status", "unknown"),
            "expiration": market.get("expiration"),
            "tags": market.get("tags") if isinstance(market.get("tags"), list) else [],
            "source": "kalshi_rest",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    print(f"🚀 Prepared {len(payload)} entries for Supabase insert")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_kalshi()
