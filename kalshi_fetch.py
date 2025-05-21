# kalshi_fetch.py – full metadata + initial snapshot loader for Kalshi (cursor pagination)

import os
import requests
from datetime import datetime
from common import insert_to_supabase

# --- Supabase config (server‑side / CI) --------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# --- Kalshi API --------------------------------------------------------------
HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ.get('KALSHI_API_KEY')}",
    "Content-Type": "application/json",
}
EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"
MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

# -----------------------------------------------------------------------------

def safe_ts(val: str | None):
    """Return ISO string or None (for empty timestamp fields)."""
    return val.strip() if val else None

# -----------------------------------------------------------------------------
# Fetch all events once so we can enrich markets with event_name
# -----------------------------------------------------------------------------

def fetch_events() -> dict[str, dict]:
    print("📡 Fetching Kalshi events…", flush=True)
    r = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15)
    r.raise_for_status()
    events = r.json().get("events", [])
    print(f"🔍 Retrieved {len(events)} events", flush=True)
    return {e.get("ticker"): e for e in events if e.get("ticker")}

# -----------------------------------------------------------------------------
# Cursor‑based pagination (no 1000‑market cap)
# -----------------------------------------------------------------------------

def fetch_all_markets(limit: int = 1000) -> list[dict]:
    print("📡 Fetching Kalshi markets via cursor…", flush=True)
    markets, cursor = [], None
    page = 0
    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(MARKETS_URL, headers=HEADERS_KALSHI, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        batch = data.get("markets", [])
        cursor = data.get("cursor")  # will be None on last page
        if not batch:
            break
        markets.extend(batch)
        page += 1
        print(f"⏱  page {page:<3} | +{len(batch):4} markets | next cursor = {cursor}", flush=True)
        if not cursor:
            break
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

# -----------------------------------------------------------------------------
# Main ingestion routine
# -----------------------------------------------------------------------------

def main():
    events = fetch_events()
    raw_markets = fetch_all_markets()
    print(f"🏆 Markets to ingest: {len(raw_markets)}", flush=True)

    now_ts = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for m in raw_markets:
        ticker = m.get("ticker")
        if not ticker:
            continue

        ev = events.get(m.get("event_ticker")) or {}
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")

        if yes_bid is not None and no_bid is not None:
            prob = round((yes_bid + (1 - no_bid)) / 2, 4)
        elif yes_bid is not None:
            prob = round(yes_bid, 4)
        elif no_bid is not None:
            prob = round(1 - no_bid, 4)
        else:
            prob = None

        # --- markets table ----------------------------------------------------
        rows_m.append({
            "market_id": ticker,
            "market_name": m.get("title") or m.get("description") or "",
            "market_description": m.get("description") or "",
            "event_name": ev.get("title") or ev.get("name") or "",
            "event_ticker": m.get("event_ticker") or "",
            "expiration": safe_ts(m.get("expiration")),
            "tags": m.get("tags") or [],
            "source": "kalshi",
            "status": m.get("status") or "",
        })

        # --- snapshots table --------------------------------------------------
        rows_s.append({
            "market_id": ticker,
            "price": round(prob, 4) if prob is not None else None,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": m.get("volume"),
            "liquidity": m.get("open_interest"),
            "timestamp": now_ts,
            "source": "kalshi",
        })

        # --- outcomes table ---------------------------------------------------
        if yes_bid is not None:
            rows_o.append({
                "market_id": ticker,
                "outcome_name": "Yes",
                "price": yes_bid,
                "volume": None,
                "timestamp": now_ts,
                "source": "kalshi",
            })
        if no_bid is not None:
            rows_o.append({
                "market_id": ticker,
                "outcome_name": "No",
                "price": 1 - no_bid,
                "volume": None,
                "timestamp": now_ts,
                "source": "kalshi",
            })

    # --- push to Supabase -----------------------------------------------------
    print("💾 Upserting markets…", flush=True)
    insert_to_supabase("markets", rows_m)
    print("💾 Writing snapshots…", flush=True)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    print("💾 Writing outcomes…", flush=True)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    print(f"✅ Markets {len(rows_m)} | Snapshots {len(rows_s)} | Outcomes {len(rows_o)}", flush=True)

if __name__ == "__main__":
    main()
