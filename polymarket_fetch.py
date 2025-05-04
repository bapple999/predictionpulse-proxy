# polymarket_fetch.py  – full Polymarket metadata load + first snapshot
import os
import requests
from datetime import datetime
from common import insert_to_supabase   # shared helper

# ───────── endpoints ─────────
GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ─────────────────────────────
def fetch_gamma_markets(limit: int = 1000, max_pages: int = 30) -> list:
    """Paginate through the Gamma API until no rows or max_pages hit."""
    print("📡 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            print("⏳ Rate‑limited; retrying after 10 s", flush=True)
            time.sleep(10)
            continue
        r.raise_for_status()

        batch = r.json()
        if not batch:
            break

        markets.extend(batch)
        offset += limit
        pages  += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(market_id: str) -> dict | None:
    """Return CLOB JSON or None if the market isn't on CLOB (404)."""
    r = requests.get(CLOB_ENDPOINT.format(market_id), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

# ─────────────────────────────
def main() -> None:
    gamma_markets = fetch_gamma_markets()
    now_iso       = datetime.utcnow().isoformat()

    # keep active markets with some USD volume
    active = [
        m for m in gamma_markets
        if m.get("status") == "ACTIVE"
        and m.get("endDate") and m["endDate"] > now_iso
        and float(m.get("volumeUsd") or 0) > 0
    ]
    top = sorted(active, key=lambda m: float(m["volumeUsd"]), reverse=True)[:1000]
    print(f"🏆 Markets kept after filter: {len(top)}", flush=True)

    ts = datetime.utcnow().isoformat() + "Z"
    rows_markets, rows_snaps, rows_outs = [], [], []

    for g in top:
        mid = g["id"]

        clob = fetch_clob(mid)
        if not clob:                 # skip non‑CLOB markets (usually very old)
            continue

        yes_price = clob.get("yesPrice")
        no_price  = clob.get("noPrice")
        if yes_price is None or no_price is None:
            continue

        prob = (yes_price/100 + (1 - no_price/100)) / 2

        # ─ metadata row
        rows_markets.append({
            "market_id":   mid,
            "market_name": g.get("title") or g.get("slug"),
            "description": g.get("description"),
            "tags":        g.get("categories", []),
            "expiration":  g.get("endDate"),
            "source":      "polymarket",
            "status":      g["status"],
        })

        # ─ snapshot row
        rows_snaps.append({
            "market_id":  mid,
            "price":      round(prob, 4),
            "yes_bid":    yes_price/100,
            "no_bid":     no_price/100,
            "volume":     float(g.get("volumeUsd", 0)),
            "liquidity":  float(g.get("liquidity", 0)),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # ─ outcome rows
        rows_outs.extend([
            {"market_id": mid, "outcome_name": "Yes", "price": yes_price/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
            {"market_id": mid, "outcome_name": "No",  "price": 1 - no_price/100,
             "volume": None, "timestamp": ts, "source": "polymarket_clob"},
        ])

    print("💾 Writing rows to Supabase…", flush=True)
    insert_to_supabase("markets",          rows_markets)                        # UPSERT
    insert_to_supabase("market_snapshots", rows_snaps, conflict_key=None)      # INSERT
    insert_to_supabase("market_outcomes",  rows_outs,  conflict_key=None)      # INSERT

    print(f"✅ Done: Markets {len(rows_markets)}, Snapshots {len(rows_snaps)}, Outcomes {len(rows_outs)}", flush=True)

# ─────────────────────────────
if __name__ == "__main__":
    main()
