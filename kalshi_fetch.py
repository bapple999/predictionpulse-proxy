# kalshi_fetch.py  – daily (or hourly) metadata load + first snapshot for Kalshi
import os
import requests
from datetime import datetime
from common import insert_to_supabase   # shared helper in the same folder

# ─────────────────────────────────────────────────────────────
MARKETS_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets"
EVENTS_ENDPOINT  = "https://api.elections.kalshi.com/trade-api/v2/events"

# Public endpoints: no auth header required
HEADERS = {"User-Agent": "prediction-pulse-loader/1.0"}

# ─────────────────────────────────────────────────────────────
def fetch_events() -> dict:
    print("📡 Fetching Kalshi events…", flush=True)
    r = requests.get(EVENTS_ENDPOINT, headers=HEADERS, timeout=15)
    r.raise_for_status()
    events = r.json().get("events", [])
    print(f"🔍 Retrieved {len(events)} events", flush=True)

    out = {}
    for e in events:
        key = e.get("ticker") or e.get("event_ticker")
        if key:
            out[key] = e
    return out

def fetch_all_markets(limit: int = 1000) -> list:
    print("📡 Fetching Kalshi markets (paged)…", flush=True)
    markets, offset = [], 0
    while True:
        resp = requests.get(
            MARKETS_ENDPOINT,
            headers=HEADERS,                  # keep your existing HEADERS var
            params={"limit": limit, "offset": offset},
            timeout=15,
        )
        # 502 / 504 often means we've paged past the real end
        if resp.status_code in (502, 504):
            print(f"⚠️  50x at offset {offset} → assuming end of list", flush=True)
            break
        resp.raise_for_status()

        batch = resp.json().get("markets", [])
        if not batch:
            break

        markets.extend(batch)
        offset += limit
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)

        # 🔒 safety brake: when API returns < limit rows, we've reached the end
        if len(batch) < limit:
            break

    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets


# ─────────────────────────────────────────────────────────────
def main() -> None:
    events      = fetch_events()
    now_iso     = datetime.utcnow().isoformat()
    markets_raw = fetch_all_markets()

    # keep only unexpired markets with non‑zero volume
    valid = [
        m for m in markets_raw
        if m.get("expiration") and m["expiration"] > now_iso
        and float(m.get("volume", 0)) > 0
    ]
    top = sorted(valid, key=lambda m: float(m["volume"]), reverse=True)[:1000]
    print(f"🏆 Markets kept after filter: {len(top)}", flush=True)

    ts = datetime.utcnow().isoformat() + "Z"
    rows_markets, rows_snaps, rows_outs = [], [], []

    for m in top:
        mid     = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid  = m.get("no_bid")
        prob    = (
            (yes_bid + (1 - no_bid)) / 2
            if yes_bid is not None and no_bid is not None
            else None
        )

        rows_markets.append(
            {
                "market_id":          mid,
                "market_name":        m.get("title"),
                "market_description": m.get("description"),
                "event_name":         events.get(m.get("event_ticker"), {}).get("title"),
                "event_ticker":       m.get("event_ticker"),
                "expiration":         m.get("expiration"),
                "tags":               m.get("tags", []),   # stored as jsonb
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
            rows_outs.append(
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
            rows_outs.append(
                {
                    "market_id":   mid,
                    "outcome_name":"No",
                    "price":        1 - no_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                }
            )

    print("💾 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets",          rows_markets)                        # upsert
    insert_to_supabase("market_snapshots", rows_snaps, conflict_key=None)      # plain insert
    insert_to_supabase("market_outcomes",  rows_outs,  conflict_key=None)      # plain insert

    print(
        f"✅ Markets {len(rows_markets)} | "
        f"Snapshots {len(rows_snaps)} | Outcomes {len(rows_outs)}",
        flush=True,
    )

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
