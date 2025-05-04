# polymarket_update_prices.py  – runs every 5 min
import requests, time, os
from datetime import datetime
from common import insert_to_supabase            # shared helper

# ───────── endpoints ─────────
GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ───────── helpers ───────────
existing_ids = set()   # simple in‑memory cache during one run

def ensure_market_exists(gamma_row: dict):
    """If the metadata row isn't in Supabase yet, insert a minimal one."""
    mid = gamma_row["id"]
    if mid in existing_ids:
        return
    existing_ids.add(mid)

    row = {
        "market_id":   mid,
        "market_name": gamma_row.get("title") or gamma_row.get("slug", ""),
        "source":      "polymarket",
        "status":      gamma_row.get("status"),
    }
    insert_to_supabase("markets", [row])   # UPSERT on market_id

def fetch_active_markets(limit: int = 1000, max_pages: int = 20) -> list:
    print("📡 Fetching active Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    now = datetime.utcnow().isoformat()

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

        active = [m for m in batch if m.get("endDate") and m["endDate"] > now]
        markets.extend(active)
        offset += limit
        pages  += 1
        print(f"⏱ {len(active):4} active markets (offset {offset})", flush=True)

    print(f"🔍 Total active markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str) -> dict | None:
    """Return CLOB data or None if not tradable on CLOB."""
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

# ───────── main routine ───────
def main() -> None:
    active_markets = fetch_active_markets()
    ts = datetime.utcnow().isoformat() + "Z"

    snaps, outs = [], []

    for g in active_markets:
        mid = g["id"]
        clob = fetch_clob(mid)
        if not clob:
            continue

        yes = clob.get("yesPrice")
        no  = clob.get("noPrice")
        if yes is None or no is None:
            continue

        ensure_market_exists(g)

        prob = (yes/100 + (1 - no/100)) / 2

        snaps.append({
            "market_id":  mid,
            "price":      round(prob, 4),
            "yes_bid":    yes/100,
            "no_bid":     no/100,
            "volume":     float(g.get("volumeUsd", 0)),
            "liquidity":  float(g.get("liquidity", 0)),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        outs.extend([
            {"market_id": mid, "outcome_name":"Yes", "price": yes/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
            {"market_id": mid, "outcome_name":"No",  "price": 1 - no/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
        ])

    print("💾 Writing snapshots/outcomes to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snaps, conflict_key=None)    # plain INSERT
    insert_to_supabase("market_outcomes",  outs,  conflict_key=None)

    print(f"✅ Snapshots {len(snaps)} | Outcomes {len(outs)}", flush=True)

# ─────────────────────────────
if __name__ == "__main__":
    main()
