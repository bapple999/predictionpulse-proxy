# kalshi_update_prices.py – lightweight snapshot updater for Kalshi

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
    print("📡 Fetching updated Kalshi prices (paged)…", flush=True)
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
    print(f"🔄 Updated market count: {len(markets)}", flush=True)
    return markets

def main():
    ts = datetime.utcnow().isoformat() + "Z"
    markets = fetch_all_markets()

    snapshots, outcomes = [], []

    for m in markets:
        mid     = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid  = m.get("no_bid")
        prob    = (
            (yes_bid + (1 - no_bid)) / 2
            if yes_bid is not None and no_bid is not None
            else None
        )

        snapshots.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi",
        })

        if yes_bid is not None and no_bid is not None:
            outcomes.extend([
                {
                    "market_id":    mid,
                    "outcome_name": "Yes",
                    "price":        yes_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                },
                {
                    "market_id":    mid,
                    "outcome_name": "No",
                    "price":        1 - no_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                },
            ])

    print("💾 Writing snapshots to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    print("💾 Writing outcomes to Supabase…", flush=True)
    insert_to_supabase("market_outcomes",  outcomes, conflict_key=None)
    print(f"✅ Snapshots {len(snapshots)} | Outcomes {len(outcomes)}", flush=True)

if __name__ == "__main__":
    main()
