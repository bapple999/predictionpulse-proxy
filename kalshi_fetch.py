# ✅ kalshi_fetch.py
import os
import requests
from datetime import datetime
from common import insert_to_supabase

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ.get('KALSHI_API_KEY')}",
    "Content-Type": "application/json",
}
EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"
MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

def safe_ts(val: str | None):
    return val.strip() if val else None

def fetch_events():
    r = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15)
    r.raise_for_status()
    events = r.json().get("events", [])
    return {e.get("ticker"): e for e in events if e.get("ticker")}

def fetch_all_markets(limit: int = 1000):
    markets, cursor = [], None
    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(MARKETS_URL, headers=HEADERS_KALSHI, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        batch = data.get("markets", [])
        cursor = data.get("cursor")
        if not batch:
            break
        markets.extend(batch)
        if not cursor:
            break
    return markets

def main():
    events = fetch_events()
    raw_markets = fetch_all_markets()

    # Top 200 by volume
    top_markets = sorted(
        [m for m in raw_markets if isinstance(m.get("volume"), (int, float))],
        key=lambda x: x["volume"],
        reverse=True
    )[:200]

    now_ts = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for m in top_markets:
        ticker = m.get("ticker")
        if not ticker:
            continue

        ev = events.get(m.get("event_ticker")) or {}

        last_price = m.get("last_price")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        volume = m.get("volume")
        liquidity = m.get("open_interest")
        expiration = safe_ts(m.get("expiration"))

        rows_m.append({
            "market_id": ticker,
            "market_name": m.get("title") or m.get("description") or "",
            "market_description": m.get("description") or "",
            "event_name": ev.get("title") or ev.get("name") or "",
            "event_ticker": m.get("event_ticker") or "",
            "expiration": expiration,
            "tags": m.get("tags") or [],
            "source": "kalshi",
            "status": m.get("status") or "",
        })

        rows_s.append({
            "market_id": ticker,
            "price": round(last_price, 4) if last_price is not None else None,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": volume,
            "liquidity": liquidity,
            "expiration": expiration,
            "timestamp": now_ts,
            "source": "kalshi",
        })

        rows_o.append({
            "market_id": ticker,
            "outcome_name": "Yes",
            "price": last_price,
            "volume": volume,
            "timestamp": now_ts,
            "source": "kalshi",
        })

    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

if __name__ == "__main__":
    main()
