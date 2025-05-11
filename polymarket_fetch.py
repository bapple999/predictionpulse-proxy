# polymarket_fetch.py – full metadata + first snapshot
import requests, time, json, itertools
from datetime import datetime
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

def get_field(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default

def market_status(expiration_iso: str) -> str:
    return "TRADING" if expiration_iso > datetime.utcnow().isoformat() else "CLOSED"

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
        batch = r.json()
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
    gamma = fetch_gamma_markets()
    now_iso = datetime.utcnow().isoformat()
    ts = now_iso + "Z"

    def is_live(m):
        end_date = get_field(m, "endDate", "endTime", "end_time", default="1970")
        return end_date > now_iso

    live = [m for m in gamma if is_live(m)]
    print(f"🏆 Markets kept after filter: {len(live)}", flush=True)

    rows_m, rows_s, rows_o = [], [], []

    for g in live:
        mid   = g["id"]
        end_d = get_field(g, "endDate", "endTime", "end_time")
        event_name = get_field(g, "question", "slug", "title", default="")

        tags = g.get("categories") or ([g.get("category")] if g.get("category") else [])

        rows_m.append({
            "market_id":          mid,
            "market_name":        get_field(g, "title", "question", "slug", default=""),
            "market_description": g.get("description"),
            "event_name":         event_name,
            "event_ticker":       g.get("slug") or mid,
            "expiration":         end_d,
            "tags":               tags,
            "source":             "polymarket",
            "status":             get_field(g, "status", "state") or market_status(end_d),
        })

        clob = fetch_clob(mid)
        outcomes = clob.get("outcomes", []) if clob else []

        # Estimate midpoint probability for binary market if possible
        prob = None
        if len(outcomes) == 2:
            try:
                prices = [o.get("price") for o in outcomes if o.get("price") is not None]
                if len(prices) == 2:
                    prob = (prices[0]/100 + (1 - prices[1]/100)) / 2
            except Exception as e:
                print(f"⚠️ Error calculating prob for market {mid}: {e}")

        rows_s.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    None,
            "no_bid":     None,
            "volume":     float(g.get("volume24Hr") or 0),
            "liquidity":  float(g.get("liquidity") or 0),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        if not outcomes:
            print(f"⚠️ No outcomes returned for market {mid}")

        for outcome in outcomes:
            name = outcome.get("name")
            price = outcome.get("price")
            if name and price is not None:
                rows_o.append({
                    "market_id":    mid,
                    "outcome_name": name,
                    "price":        price / 100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket_clob",
                })

    print("📏 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    print(f"✅ Done: Markets {len(rows_m)}, Snapshots {len(rows_s)}, Outcomes {len(rows_o)}", flush=True)

if __name__ == "__main__":
    main()
