import os, requests, time
from datetime import datetime
from scripts.common import insert_to_supabase   # adjust if your package name differs

ROOT_API         = "https://api.elections.kalshi.com/trade-api/v2"
MARKETS_ENDPOINT = f"{ROOT_API}/markets"
EVENTS_ENDPOINT  = f"{ROOT_API}/events"
HEADERS_KALSHI   = {"Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"}

def fetch_events():
    r = requests.get(EVENTS_ENDPOINT, headers=HEADERS_KALSHI, timeout=15)
    r.raise_for_status()
    return {e["ticker"]: e for e in r.json().get("events", [])}

def fetch_all_markets(limit=100):
    markets, offset = [], 0
    while True:
        r = requests.get(MARKETS_ENDPOINT,
                         headers=HEADERS_KALSHI,
                         params={"limit": limit, "offset": offset},
                         timeout=15)
        r.raise_for_status()
        batch = r.json().get("markets", [])
        if not batch:
            break
        markets.extend(batch)
        offset += limit
        time.sleep(0.1)          # polite pacing
    return markets

def main():
    events      = fetch_events()
    now_iso     = datetime.utcnow().isoformat()
    markets_raw = fetch_all_markets()

    # keep only unexpired markets with non‑zero volume
    valid = [m for m in markets_raw
             if m.get("expiration") and m["expiration"] > now_iso
             and float(m.get("volume", 0)) > 0]

    top = sorted(valid, key=lambda m: float(m["volume"]), reverse=True)[:1000]
    ts  = datetime.utcnow().isoformat() + "Z"

    rows_markets, rows_snaps, rows_outcomes = [], [], []

    for m in top:
        mid      = m["ticker"]
        yes_bid  = m.get("yes_bid")
        no_bid   = m.get("no_bid")
        prob     = ((yes_bid + (1 - no_bid)) / 2
                     if yes_bid is not None and no_bid is not None else None)

        rows_markets.append({
            "market_id":          mid,
            "market_name":        m.get("title"),
            "market_description": m.get("description"),
            "event_name":         events.get(m.get("event_ticker"), {}).get("title"),
            "event_ticker":       m.get("event_ticker"),
            "expiration":         m.get("expiration"),
            "tags":               m.get("tags", []),   # stored as jsonb
            "source":             "kalshi",
            "status":             m.get("status")
        })

        rows_snaps.append({
            "market_id": mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi"
        })

        if yes_bid is not None:
            rows_outcomes.append({
                "market_id":   mid,
                "outcome_name":"Yes",
                "price":        yes_bid,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })
        if no_bid is not None:
            rows_outcomes.append({
                "market_id":   mid,
                "outcome_name":"No",
                "price":        1 - no_bid,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })

    insert_to_supabase("markets",          rows_markets)
    insert_to_supabase("market_snapshots", rows_snaps)
    insert_to_supabase("market_outcomes",  rows_outcomes)

if __name__ == "__main__":
    main()
