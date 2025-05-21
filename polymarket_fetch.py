# polymarket_fetch.py – rewritten for parity with Kalshi ingestion

import requests, time
from datetime import datetime
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

def fetch_gamma_markets(limit=1000, max_pages=30):
    print("📱 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset = [], 0
    while len(markets) < limit * max_pages:
        r = requests.get(GAMMA_ENDPOINT, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            print("⏳ Rate-limited; sleeping 10s", flush=True)
            time.sleep(10); continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        markets.extend(batch)
        offset += limit
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def main():
    gamma = fetch_gamma_markets()
    now_iso = datetime.utcnow().isoformat()
    ts = now_iso + "Z"

    rows_m, rows_s, rows_o = [], [], []

    for g in gamma:
        mid = g.get("id")
        title = g.get("title") or g.get("question") or ""
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if not end_d or not mid:
            continue

        clob = fetch_clob(mid)
        outcomes = clob.get("outcomes", []) if clob else []

        # Binary markets (e.g. YES/NO)
        if len(outcomes) == 2 and all(o.get("price") is not None for o in outcomes):
            yes_price = outcomes[0]["price"]
            no_price  = outcomes[1]["price"]
            prob = round((yes_price/100 + (1 - no_price/100)) / 2, 4)
            yes_bid = yes_price / 100
            no_bid  = no_price / 100
        else:
            prob = None
            yes_bid = no_bid = None

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
            "price":     prob,
            "yes_bid":   yes_bid,
            "no_bid":    no_bid,
            "volume":    float(g.get("volume24Hr") or 0),
            "liquidity": float(g.get("liquidity") or 0),
            "expiration": end_d,
            "timestamp": ts,
            "source":    "polymarket",
        })

        for o in outcomes:
            name  = o.get("name")
            price = o.get("price")
            if name and price is not None:
                rows_o.append({
                    "market_id":    mid,
                    "outcome_name": name,
                    "price":        price / 100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket",
                })

    print("💾 Writing to Supabase…", flush=True)
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    print(f"✅ Markets: {len(rows_m)} | Snapshots: {len(rows_s)} | Outcomes: {len(rows_o)}", flush=True)

if __name__ == "__main__":
    main()
