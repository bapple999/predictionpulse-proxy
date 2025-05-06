# kalshi_fetch.py  – hourly metadata + snapshot loader for Kalshi
import os
import requests
from datetime import datetime
from common import insert_to_supabase   # shared helper

MARKETS_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets"
EVENTS_ENDPOINT  = "https://api.elections.kalshi.com/trade-api/v2/events"
HEADERS          = {"User-Agent": "prediction-pulse-loader/1.1"}

def fetch_events() -> dict:
    print("📡 Fetching Kalshi events…", flush=True)
    r = requests.get(EVENTS_ENDPOINT, headers=HEADERS, timeout=15)
    r.raise_for_status()
    events = r.json().get("events", [])
    print(f"🔍 Retrieved {len(events)} events", flush=True)
    return {
        e.get("ticker") or e.get("event_ticker"): e
        for e in events
        if e.get("ticker") or e.get("event_ticker")
    }

def fetch_all_markets(limit: int = 1000) -> list:
    print("📡 Fetching Kalshi markets (paged)…", flush=True)
    markets, offset = [], 0
    seen_ids = set()

    while True:
        resp = requests.get(
            MARKETS_ENDPOINT,
            headers=HEADERS,
            params={"limit": limit, "offset": offset},
            timeout=15,
        )
        if resp.status_code in (502, 504):
            print(f"⚠️ 50x at offset {offset} → assuming end", flush=True)
            break
        resp.raise_for_status()

        batch = resp.json().get("markets", [])
        if not batch:
            break

        # detect repeated pages
        batch_ids = [m["ticker"] for m in batch]
        if any(mid in seen_ids for mid in batch_ids):
            print(f"🔒 Duplicate batch at offset {offset} → stopping", flush=True)
            break
        seen_ids.update(batch_ids)

        markets.extend(batch)
        offset += limit
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)

        # safety: if the API ever returned fewer than `limit`, we're at the end
        if len(batch) < limit:
            break

    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets


def is_active(m: dict, now_iso: str) -> bool:
    # 1) must have expiration in the future
    exp = m.get("expiration")
    if not exp or exp <= now_iso:
        return False
    # 2) or have volume
    if float(m.get("volume", 0)) > 0:
        return True
    # 3) or have open interest
    if float(m.get("open_interest", 0)) > 0:
        return True
    # 4) or both bids exist
    if m.get("yes_bid") is not None and m.get("no_bid") is not None:
        return True
    return False

def main() -> None:
    events      = fetch_events()
    now_iso     = datetime.utcnow().isoformat()
    markets_raw = fetch_all_markets()

    valid = [m for m in markets_raw if is_active(m, now_iso)]
    print(f"🏆 Markets kept after filters: {len(valid)}", flush=True)

    # rank by volume (fallback 0) and take top 1000
    top = sorted(valid, key=lambda m: float(m.get("volume", 0)), reverse=True)[:1000]

    ts = datetime.utcnow().isoformat() + "Z"
    rows_markets, rows_snaps, rows_outs = [], [], []

    for m in top:
        mid, yes, no = m["ticker"], m.get("yes_bid"), m.get("no_bid")
        prob = (yes + (1 - no)) / 2 if yes is not None and no is not None else None

        # ── metadata row (UPSERT) ───────────────────────────────
        rows_markets.append({
            "market_id":          mid,
            "market_name":        m.get("title"),
            "market_description": m.get("description"),
            "event_name":         events.get(m.get("event_ticker"), {}).get("title"),
            "event_ticker":       m.get("event_ticker"),
            "expiration":         m.get("expiration"),
            "tags":               m.get("tags", []),
            "source":             "kalshi",
            "status":             m.get("status"),
        })

        # ── snapshot row ────────────────────────────────────────
        rows_snaps.append({
            "market_id": mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes,
            "no_bid":     no,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi",
        })

        # ── outcome rows ────────────────────────────────────────
        if yes is not None:
            rows_outs.append({
                "market_id": mid,
                "outcome_name": "Yes",
                "price": yes,
                "volume": None,
                "timestamp": ts,
                "source": "kalshi",
            })
        if no is not None:
            rows_outs.append({
                "market_id": mid,
                "outcome_name": "No",
                "price": 1 - no,
                "volume": None,
                "timestamp": ts,
                "source": "kalshi",
            })

    print("💾 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets",          rows_markets)          # UPSERT
    insert_to_supabase("market_snapshots", rows_snaps, conflict_key=None)
    insert_to_supabase("market_outcomes",  rows_outs,  conflict_key=None)

    print(
        f"✅ Markets {len(rows_markets)} | "
        f"Snapshots {len(rows_snaps)} | Outcomes {len(rows_outs)}",
        flush=True,
    )

if __name__ == "__main__":
    main()
