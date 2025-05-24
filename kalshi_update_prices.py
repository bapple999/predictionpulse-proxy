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


# ✅ polymarket_fetch.py – optimized to use YES outcome price, top 200 by contract volume

import requests, time
from datetime import datetime
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

def fetch_gamma_markets(limit=1000, max_pages=30):
    markets, offset = [], 0
    while len(markets) < limit * max_pages:
        r = requests.get(GAMMA_ENDPOINT, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            time.sleep(10); continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        markets.extend(batch)
        offset += limit
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def main():
    gamma_all = fetch_gamma_markets()
    now_iso = datetime.utcnow().isoformat()
    ts = now_iso + "Z"

    gamma = sorted(
        [g for g in gamma_all if isinstance(g.get("volume24Hr"), (int, float))],
        key=lambda g: g["volume24Hr"],
        reverse=True
    )[:200]

    rows_m, rows_s, rows_o = [], [], []

    for g in gamma:
        mid = g.get("id")
        title = g.get("title") or g.get("question") or ""
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if not end_d or not mid:
            continue

        clob = fetch_clob(mid)
        outcomes = clob.get("outcomes", []) if clob else []

        if len(outcomes) == 2 and all(o.get("price") is not None for o in outcomes):
            yes_price = outcomes[0]["price"]
            price = yes_price / 100
        else:
            price = None

        rows_m.append({
            "market_id":          mid,
            "market_name":        title,
            "market_description": g.get("description"),
            "event_name":         title,
            "event_ticker":       g.get("slug") or mid,
            "expiration":         end_d,
            "tags":               g.get("categories") or [],
            "source":             "polymarket",
            "status":             g.get("status") or "TRADING",
        })

        rows_s.append({
            "market_id": mid,
            "price":     round(price, 4) if price is not None else None,
            "yes_bid":   None,
            "no_bid":    None,
            "volume":    float(g.get("volume24Hr") or 0),
            "liquidity": float(g.get("liquidity") or 0),
            "expiration": end_d,
            "timestamp": ts,
            "source":    "polymarket",
        })

        for o in outcomes:
            name  = o.get("name")
            outcome_price = o.get("price")
            if name and outcome_price is not None:
                rows_o.append({
                    "market_id":    mid,
                    "outcome_name": name,
                    "price":        outcome_price / 100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket",
                })

    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

if __name__ == "__main__":
    main()
