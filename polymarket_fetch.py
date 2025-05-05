# polymarket_fetch.py  – full Polymarket metadata + first snapshot
import requests, time, json, itertools
from datetime import datetime
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ---------- helpers ----------
def get_field(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default

def market_status(expiration_iso: str) -> str:
    return "TRADING" if expiration_iso > datetime.utcnow().isoformat() else "CLOSED"

def clob_prices(clob: dict):
    """Return yes, no prices in cents (or None, None)."""
    if "yesPrice" in clob and "noPrice" in clob:
        return clob["yesPrice"], clob["noPrice"]
    # fallback: scan outcomes array
    outs = {o.get("name"): o.get("price") for o in clob.get("outcomes", [])}
    return outs.get("Yes"), outs.get("No")

# ---------- pagination ----------
def fetch_gamma_markets(limit=1000, max_pages=30):
    print("📡 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT,
                         params={"limit": limit, "offset": offset},
                         timeout=15)
        if r.status_code == 429:
            print("⏳ Rate‑limited; sleeping 10 s", flush=True)
            time.sleep(10); continue
        r.raise_for_status()
        batch = r.json()
        if not batch: break
        markets.extend(batch); offset += limit; pages += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()

# ---------- main ----------
def main():
    gamma = fetch_gamma_markets()

    # diagnostic — remove later
    print("🧪 First raw market from Gamma ↓", flush=True)
    for sample in itertools.islice(gamma, 0, 3):
        print(json.dumps(sample, indent=2)[:800], flush=True)

    now_iso = datetime.utcnow().isoformat()

    def is_live(m):           # only check endDate in future
        end_date = get_field(m, "endDate", "endTime", "end_time", default="1970")
        return end_date > now_iso

    live = [m for m in gamma if is_live(m)]
    top  = live[:1000]
    print(f"🏆 Markets kept after filter: {len(top)}", flush=True)

    ts   = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for g in top:
        mid   = g["id"]
        end_d = get_field(g, "endDate", "endTime", "end_time")

        # ---------- metadata ----------
        rows_m.append({
            "market_id":          mid,
            "market_name":        get_field(g, "title", "question", "slug", default=""),
            "market_description": g.get("description"),
            "tags":               g.get("categories") or [g.get("category")] if g.get("category") else [],
            "expiration":         end_d,
            "source":             "polymarket",
            "status":             get_field(g, "status", "state") or market_status(end_d),
        })

        clob = fetch_clob(mid)
        yes, no = (None, None)
        if clob:
            yes, no = clob_prices(clob)

        # ---------- snapshot ----------
        prob = (yes/100 + (1 - no/100)) / 2 if yes is not None and no is not None else None
        rows_s.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes/100 if yes is not None else None,
            "no_bid":     no/100  if no  is not None else None,
            "volume":     None,
            "liquidity":  float(g.get("liquidity", 0)),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # ---------- outcomes ----------
        if yes is not None and no is not None:
            rows_o.extend([
                {"market_id": mid, "outcome_name":"Yes", "price": yes/100,
                 "volume": None, "timestamp": ts, "source": "polymarket_clob"},
                {"market_id": mid, "outcome_name":"No",  "price": 1 - no/100,
                 "volume": None, "timestamp": ts, "source": "polymarket_clob"},
            ])

    print("💾 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets",          rows_m)                        # UPSERT
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)    # INSERT
    insert_to_supabase("market_outcomes",  rows_o, conflict_key=None)    # INSERT

    print(f"✅ Done: Markets {len(rows_m)}, Snapshots {len(rows_s)}, Outcomes {len(rows_o)}", flush=True)

# -------------------------------------------------------
if __name__ == "__main__":
    main()
