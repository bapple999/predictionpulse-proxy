# polymarket_update_prices.py  – 5 min snapshot/updater for Polymarket
import requests, time, os
from datetime import datetime
from common import insert_to_supabase   # shared helper

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ───────── helpers ───────────
def get_field(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default

def market_status(end_iso: str) -> str:
    return "TRADING" if end_iso > datetime.utcnow().isoformat() else "CLOSED"

def clob_prices(clob: dict):
    """Return (yesPrice, noPrice) in cents, or (None,None)."""
    if "yesPrice" in clob and "noPrice" in clob:
        return clob["yesPrice"], clob["noPrice"]
    outs = {o.get("name"): o.get("price") for o in clob.get("outcomes", [])}
    return outs.get("Yes"), outs.get("No")

def fetch_active_markets(limit=1000, max_pages=20):
    print("📡 Fetching active Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    now = datetime.utcnow().isoformat()

    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT,
                         params={"limit": limit, "offset": offset},
                         timeout=15)
        if r.status_code == 429:
            print("⏳ Rate‑limited; sleeping 10 s", flush=True)
            time.sleep(10)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break

        # keep only unexpired
        active = [
            m for m in batch
            if get_field(m, "endDate", "endTime", "end_time", default="1970") > now
        ]
        markets.extend(active)
        offset += limit; pages += 1
        print(f"⏱  {len(active):4} active markets (offset {offset})", flush=True)

    print(f"🔍 Total active markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

# ───────── main routine ───────
def main():
    active = fetch_active_markets()
    ts = datetime.utcnow().isoformat() + "Z"

    # build metadata rows, snapshots, and outcomes in batch
    rows_m, rows_s, rows_o = [], [], []

    for g in active:
        mid       = g["id"]
        end_iso   = get_field(g, "endDate", "endTime", "end_time")
        category  = g.get("category", "")

        # market metadata
        rows_m.append({
            "market_id":          mid,
            "market_name":        get_field(g, "title", "question", "slug", default=""),
            "market_description": g.get("description"),
            "event_name":         category,   # Polymarket proxy
            "event_ticker":       category,   # same proxy
            "tags":               g.get("categories") or ([category] if category else []),
            "expiration":         end_iso,
            "source":             "polymarket",
            "status":             get_field(g, "status", "state") or market_status(end_iso),
        })

        # price logic
        clob      = fetch_clob(mid)
        yes, no   = (None, None)
        if clob:
            yes, no = clob_prices(clob)

        # fallback to Gamma’s probability
        prob_field = get_field(g, "probability", default=None)
        if yes is None and prob_field is not None:
            yes = prob_field * 100
            no  = (1 - prob_field) * 100

        # implied probability
        prob = (yes/100 + (1 - no/100)) / 2 if yes is not None and no is not None else None

        # 24 h volume fallback
        volume24h = float(
            get_field(g, "volumeUsd24h", "volumeUSD", default=0)
        ) or None

        # snapshot row
        rows_s.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes/100 if yes is not None else None,
            "no_bid":     no/100  if no  is not None else None,
            "volume":     volume24h,
            "liquidity":  float(g.get("liquidity", 0)),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # outcomes (only when we have bids)
        if yes is not None and no is not None:
            rows_o.extend([
                {
                    "market_id":    mid,
                    "outcome_name": "Yes",
                    "price":        yes/100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket_clob",
                },
                {
                    "market_id":    mid,
                    "outcome_name": "No",
                    "price":        1 - no/100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket_clob",
                },
            ])

    print("💾 Upserting markets…", flush=True)
    insert_to_supabase("markets", rows_m)  # upsert all in one request

    print("💾 Writing snapshots/outcomes to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes",  rows_o, conflict_key=None)

    print(f"✅ Snapshots {len(rows_s)} | Outcomes {len(rows_o)}", flush=True)

if __name__ == "__main__":
    main()
