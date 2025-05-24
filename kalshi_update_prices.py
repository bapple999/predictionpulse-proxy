# ✅ kalshi_update_prices.py – uses last traded price

import os
import requests
from datetime import datetime
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

def fetch_all_markets(limit=1000):
    markets, seen, offset = [], set(), 0
    while True:
        resp = requests.get(
            MARKETS_URL,
            params={"limit": limit, "offset": offset},
            timeout=20
        )
        resp.raise_for_status()
        batch = resp.json().get("markets", [])
        if not batch:
            break
        tickers = [m.get("ticker") for m in batch if m.get("ticker")]
        if any(t in seen for t in tickers):
            break
        seen.update(tickers)
        markets.extend(batch)
        offset += limit
        if len(batch) < limit:
            break
    return markets

def main():
    ts = datetime.utcnow().isoformat() + "Z"
    markets = fetch_all_markets()

    top_markets = sorted(
        [m for m in markets if isinstance(m.get("volume"), (int, float))],
        key=lambda m: m["volume"],
        reverse=True
    )[:200]

    snapshots, outcomes = [] , []

    for m in top_markets:
        mid = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        last_price = m.get("last_price")

        snapshots.append({
            "market_id":  mid,
            "price":      round(last_price, 4) if last_price is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi",
        })

        title = m.get("title") or m.get("description") or mid
        if last_price is not None:
            outcomes.append({
                "market_id":    mid,
                "outcome_name": title,
                "price":        last_price,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi",
            })

    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)

if __name__ == "__main__":
    main()
