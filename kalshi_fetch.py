# kalshi_fetch.py  ── daily full‑market load for Kalshi
import os
import requests, time
from datetime import datetime
from common import insert_to_supabase

ROOT_API         = "https://api.elections.kalshi.com/trade-api/v2"
MARKETS_ENDPOINT = f"{ROOT_API}/markets"
EVENTS_ENDPOINT  = f"{ROOT_API}/events"

HEADERS_KALSHI   = {"User-Agent": "prediction-pulse-loader"}  # public endpoints need no auth

# ────────────────────────────────────────────────────────────
def fetch_events() -> dict:
    """Return {event_ticker: event_object}, tolerate missing 'ticker' key."""
    r = requests.get(EVENTS_ENDPOINT, timeout=15)
    r.raise_for_status()

    ev_map = {}
    for e in r.json().get("events", []):
        key = e.get("ticker") or e.get("event_ticker")
        if key:
            ev_map[key] = e
    return ev_map

def fetch_all_markets(limit: int = 1000) -> list:
    """Download every market page until the API says 'no more'."""
    markets, offset = [], 0
    while True:
        try:
            r = requests.get(
                MARKETS_ENDPOINT,
                params={"limit": limit, "offset": offset},
                timeout=15,
            )
            # 502/504 often means we've paged past the end — treat as EOF
            if r.status_code in (502, 504):
                break
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            # log and break; avoids job crash
            print(f"⚠️  pagination stopped at offset {offset} → {e}")
            break

        batch = r.json().get("markets", [])
        if not batch:
            break
        markets.extend(batch)
        offset += limit
    return markets


# ────────────────────────────────────────────────────────────
def main() -> None:
    events      = fetch_events()
    now_iso     = datetime.utcnow().isoformat()
    markets_raw = fetch_all_markets()

    valid = [
        m for m in markets_raw
        if m.get("expiration") and m["expiration"] > now_iso
        and float(m.get("volume", 0)) > 0
    ]

    top = sorted(valid, key=lambda m: float(m["volume"]), reverse=True)[:1000]
    ts  = datetime.utcnow().isoformat() + "Z"

    rows_markets, rows_snaps, rows_outcomes = [], [], []

    for m in top:
        mid     = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid  = m.get("no_bid")
        prob    = (
            (yes_bid + (1 - no_bid)) / 2
            if yes_bid is not None and no_bid is not None else None
        )

        rows_markets.append(
            {
                "market_id":          mid,
                "market_name":        m.get("title"),
                "market_description": m.get("description"),
                "event_name":         events.get(m.get("event_ticker"), {}).get("title"),
                "event_ticker":       m.get("event_ticker"),
                "expiration":         m.get("expiration"),
                "tags":               m.get("tags", []),
                "source":             "kalshi",
                "status":             m.get("status"),
            }
        )

        rows_snaps.append(
            {
                "market_id":  mid,
                "price":      round(prob, 4) if prob is not None else None,
                "yes_bid":    yes_bid,
                "no_bid":     no_bid,
                "volume":     m.get("volume"),
                "liquidity":  m.get("open_interest"),
                "timestamp":  ts,
                "source":     "kalshi",
            }
        )

        if yes_bid is not None:
            rows_outcomes.append(
                {
                    "market_id":   mid,
                    "outcome_name":"Yes",
                    "price":        yes_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                }
            )
        if no_bid is not None:
            rows_outcomes.append(
                {
                    "market_id":   mid,
                    "outcome_name":"No",
                    "price":        1 - no_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                }
            )

    insert_to_supabase("markets",          rows_markets)                        # upsert
    insert_to_supabase("market_snapshots", rows_snaps, conflict_key=None)      # plain insert
    insert_to_supabase("market_outcomes",  rows_outcomes, conflict_key=None)   # plain insert

    # summary print — inside main so variables exist
    print(
        f"✅ Markets {len(rows_markets)} | "
        f"Snapshots {len(rows_snaps)} | Outcomes {len(rows_outcomes)}"
    )

# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
