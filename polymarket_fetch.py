# polymarket_fetch.py  – full Polymarket metadata load + first snapshot
import requests, time, json, itertools
from datetime import datetime
from common import insert_to_supabase          # shared helper

# ───────── endpoints ─────────
GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ───────── utilities ─────────
def get_field(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default

# ───────── pagination ────────
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
        markets.extend(batch)
        offset += limit; pages += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()

# ───────── main ──────────────
def main():
    gamma = fetch_gamma_markets()

    # ── diagnostic sample (first 3 markets) ─────────────
    print("🧪 First raw market from Gamma ↓", flush=True)
    for sample in itertools.islice(gamma, 0, 3):
        print(json.dumps(sample, indent=2)[:800], flush=True)
    # ----------------------------------------------------

    now_iso = datetime.utcnow().isoformat()

    def is_live(m):
        state       = (get_field(m, "status", "state", default="")).upper()
        status_ok   = state in ("TRADING", "OPEN", "ACTIVE")
        end_time    = get_field(m, "endTime", "end_time", default="9999")
        still_open  = end_time > now_iso
        vol         = get_field(
            m, "volumeUsd24h", "volumeUSD24h", "volumeUSD", "totalVolumeUSD", default=0
        )
        vol_ok      = float(vol) > 0
        return status_ok and still_open and vol_ok

    live = [m for m in gamma if is_live(m)]
    top  = sorted(
        live,
        key=lambda m: float(
            get_field(m, "volumeUsd24h", "volumeUSD24h", "volumeUSD", "totalVolumeUSD", default=0)
        ),
        reverse=True
    )[:1000]
    print(f"🏆 Markets kept after filter: {len(top)}", flush=True)

    ts = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for g in top:
        mid = g["id"]
        clob = fetch_clob(mid)
        if not clob: continue
        yes = clob.get("yesPrice"); no = clob.get("noPrice")
        if yes is None or no is None: continue
        prob = (yes/100 + (1 - no/100)) / 2

        rows_m.append({
            "market_id":   mid,
            "market_name": get_field(g, "title", "slug", default=""),
            "description": g.get("description"),
            "tags":        g.get("categories", []),
            "expiration":  get_field(g, "endTime", "end_time"),
            "source":      "polymarket",
            "status":      get_field(g, "status", "state"),
        })

        rows_s.append({
            "market_id": mid,
            "price":     round(prob, 4),
            "yes_bid":   yes/100,
            "no_bid":    no/100,
            "volume":    float(get_field(g, "volumeUsd24h", "volumeUSD", "totalVolumeUSD", default=0)),
            "liquidity": float(g.get("liquidity", 0)),
            "timestamp": ts,
            "source":    "polymarket_clob",
        })

        rows_o.extend([
            {"market_id": mid, "outcome_name":"Yes", "price": yes/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
            {"market_id": mid, "outcome_name":"No",  "price": 1 - no/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
        ])

    print("💾 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes",  rows_o, conflict_key=None)

    print(f"✅ Done: Markets {len(rows_m)}, Snapshots {len(rows_s)}, Outcomes {len(rows_o)}", flush=True)

# ────────────────────────────
if __name__ == "__main__":
    main()

