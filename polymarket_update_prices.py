# polymarket_update_prices.py  – 5 min snapshot/updater for Polymarket
import os, requests, time
from datetime import datetime
from common import insert_to_supabase   # shared helper

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# simple in‑memory cache to avoid duplicate UPSERTs
_existing_markets = set()

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
    # fallback: outcomes array
    outs = {o.get("name"): o.get("price") for o in clob.get("outcomes", [])}
    return outs.get("Yes"), outs.get("No")

def ensure_market_exists(g: dict):
    """UPSERT a minimal markets row if not already done this run."""
    mid = g["id"]
    if mid in _existing_markets:
        return
    _existing_markets.add(mid)

    end_iso = get_field(g, "endDate", "endTime", "end_time", default="")
    insert_to_supabase("markets", [{
        "market_id":          mid,
        "market_name":        get_field(g, "title", "question", "slug", default=""),
        "market_description": g.get("description"),
        "tags":               g.get("categories") or ([g.get("category")] if g.get("category") else []),
        "expiration":         end_iso,
        "source":             "polymarket",
        "status":             get_field(g, "status", "state") or market_status(end_iso),
    }])

def fetch_active_markets(limit: int = 1000, max_pages: int = 20) -> list:
    """Page through Gamma, returning only still‑open markets."""
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
        # keep only unexpired
        active = [m for m in batch if get_field(m, "endDate", "endTime", "end_time", default="1970") > now]
        markets.extend(active)
        offset += limit; pages += 1
        print(f"⏱  {len(active):4} active markets (offset {offset})", flush=True)
    print(f"🔍 Total active markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    """Fetch CLOB data or return None if not on CLOB."""
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def main():
    active = fetch_active_markets()
    ts = datetime.utcnow().isoformat() + "Z"

    snapshots, outcomes = [], []

    for g in active:
        mid = g["id"]
        ensure_market_exists(g)

        clob = fetch_clob(mid)
        yes, no = (None, None)
        if clob:
            yes, no = clob_prices(clob)

        # fallback to Gamma probability if available
        gamma_prob = get_field(g, "probability", default=None)
        if yes is None and gamma_prob is not None:
            yes = gamma_prob * 100
            no  = (1 - gamma_prob) * 100

        # compute implied prob
        prob = (
            (yes/100 + (1 - no/100)) / 2
            if yes is not None and no is not None
            else None
        )

        # always write a snapshot row
        snapshots.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes/100 if yes is not None else None,
            "no_bid":     no/100  if no  is not None else None,
            "volume":     float(get_field(g, "volumeUsd24h", "volumeUSD", default=0)) or None,
            "liquidity":  float(g.get("liquidity", 0)),
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # only write outcomes when prices exist
        if yes is not None and no is not None:
            outcomes.extend([
                {
                    "market_id": mid,
                    "outcome_name": "Yes",
                    "price": yes / 100,
                    "volume": None,
                    "timestamp": ts,
                    "source": "polymarket_clob",
                },
                {
                    "market_id": mid,
                    "outcome_name": "No",
                    "price": 1 - no / 100,
                    "volume": None,
                    "timestamp": ts,
                    "source": "polymarket_clob",
                },
            ])

    print("💾 Writing snapshots/outcomes to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)
    print(f"✅ Snapshots {len(snapshots)} | Outcomes {len(outcomes)}", flush=True)

if __name__ == "__main__":
    main()
