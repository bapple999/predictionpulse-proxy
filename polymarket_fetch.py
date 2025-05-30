# ✅ polymarket_fetch.py – top 200 markets by dollar volume with YES outcome price

import requests, time
from datetime import datetime
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

def fetch_gamma_markets(limit=1000, max_pages=30):
    print("📱 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            print("⏳ Rate‑limited; sleeping 10 s", flush=True)
            time.sleep(10)
            continue
        r.raise_for_status()
        data = r.json()
        batch = data.get("markets", [])
        if not batch:
            break
        markets.extend(batch)
        offset += limit
        pages += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
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

    # filter and rank top 200 by volume
    gamma = sorted(
        [g for g in gamma_all if isinstance(g.get("volume24Hr"), (int, float))],
        key=lambda g: g["volume24Hr"],
        reverse=True
    )[:200]

    print(f"🏆 Top 200 markets selected by volume", flush=True)

    rows_m, rows_s, rows_o = [], [], []

    for g in gamma:
        mid = g.get("id")
        title = g.get("title") or g.get("question") or ""
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if not end_d or not mid:
            continue

        clob = fetch_clob(mid)
        outcomes = clob.get("outcomes", []) if clob else []

        # Try to get price of YES outcome
        yes_price = next((o["price"] for o in outcomes if o.get("name", "").lower() == "yes" and o.get("price") is not None), None)
        price = yes_price / 100 if yes_price is not None else None

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

    print(f"📦 Inserting {len(rows_m)} markets, {len(rows_s)} snapshots, {len(rows_o)} outcomes", flush=True)
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    print("✅ Done.", flush=True)

if __name__ == "__main__":
    main()
