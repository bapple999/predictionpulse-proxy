import os
import requests
from datetime import datetime

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
        ticker = event.get("ticker")
        if ticker:
            event_dict[ticker] = event
        else:
            print(f"⚠️ Skipping event with no ticker: {event}")

    print(f"📂 Loaded {len(event_dict)} valid events")
    return event_dict


def fetch_kalshi():
    print("📡 Fetching Kalshi markets...")
    res = requests.get(KALSHI_MARKETS_API, headers=HEADERS, params={"limit": 1000})
    res.raise_for_status()
    markets = res.json().get("markets", [])
    print(f"🔍 Retrieved {len(markets)} markets")

    events = fetch_events()
    markets_with_volume = [m for m in markets if m.get("volume")]
    sorted_markets = sorted(markets_with_volume, key=lambda m: m["volume"], reverse=True)[:100]

    payload = []
    for market in sorted_markets:
        yes_bid = market.get("yes_bid")
        no_bid = market.get("no_bid")
        if yes_bid is None or no_bid is None:
            continue

        prob = (yes_bid + (1 - no_bid)) / 2
        event_ticker = market.get("event_ticker", "")
        event = events.get(event_ticker, {})
        event_name = event.get("title", "") if event else ""

        payload.append({
            "market_id": market.get("ticker", ""),
            "market_name": market.get("title", ""),
            "market_description": market.get("description", ""),
            "event_name": event_name,
            "event_ticker": event_ticker,
            "price": round(prob, 4),
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": market.get("volume", 0),
            "liquidity": market.get("open_interest", 0),
            "status": market.get("status", "unknown"),
            "expiration": market.get("expiration"),
            "tags": market.get("tags") if isinstance(market.get("tags"), list) else [],
            "source": "kalshi_rest",
            "timestamp": datetime.utcnow().isoformat()
        })

    print(f"📦 Prepared {len(payload)} market entries for Supabase")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_kalshi()
