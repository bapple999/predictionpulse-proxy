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
        ticker = event.get("ticker") or event.get("event_ticker")
        if ticker:
            event_dict[ticker] = event
    print(f"📂 Loaded {len(event_dict)} valid events")
    return event_dict

def fetch_kalshi():
    print("📡 Fetching Kalshi markets...")
    res = requests.get(KALSHI_MARKETS_API, headers=HEADERS, params={"limit": 1000})
    res.raise_for_status()
    markets = res.json().get("markets", [])
    print(f"🔍 Retrieved {len(markets)} markets")

    events = fetch_events()
    now = datetime.utcnow().isoformat()
    valid_markets = []
    for market in markets:
        try:
            if not market.get("expiration") or market["expiration"] <= now:
                continue
            if float(market.get("volume", 0)) <= 0:
                continue
        except Exception:
            continue
        valid_markets.append(market)

    print(f"✅ Valid markets after filters: {len(valid_markets)}")
    sorted_markets = sorted(valid_markets, key=lambda m: float(m.get("volume", 0)), reverse=True)[:1000]

    payload = []
    for market in sorted_markets:
        try:
            yes_bid = market.get("yes_bid")
            no_bid = market.get("no_bid")
            if yes_bid is not None and no_bid is not None:
                price = (yes_bid + (1 - no_bid)) / 2
            else:
                price = 0.5

            event_ticker = market.get("event_ticker") or ""
            event = events.get(event_ticker, {})

            payload.append({
                "market_id": market.get("ticker", ""),
                "market_name": market.get("title", ""),
                "market_description": market.get("description", ""),
                "event_name": event.get("title", ""),
                "event_ticker": event_ticker,
                "price": round(price, 4),
                "yes_bid": yes_bid,
                "no_bid": no_bid,
                "volume": float(market.get("volume", 0)),
                "liquidity": float(market.get("open_interest", 0)),
                "status": market.get("status", "unknown"),
                "expiration": market.get("expiration"),
                "tags": market.get("tags") if isinstance(market.get("tags"), list) else [],
                "source": "kalshi_rest",
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"⚠️ Error processing market {market.get('ticker')}: {e}")
            continue

    print(f"🚀 Prepared {len(payload)} entries for Supabase insert")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_kalshi()
