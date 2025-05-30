# ✅ polymarket_update_prices.py – lightweight updater using YES price as market price

import os
import requests
from datetime import datetime
from common import insert_to_supabase

# Supabase config
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

# Polymarket CLOB endpoint
CLOB_ENDPOINT = "https://clob.polymarket.com/markets/{}"

# Fetch single market's CLOB data
def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

# Get all open Polymarket market IDs (expiration in the future)
def load_market_ids(now_iso: str):
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration&limit=500"
    resp = requests.get(url, headers=SUPA_HEADERS, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    market_ids = [r["market_id"] for r in rows if r.get("expiration") and r["expiration"] > now_iso]
    print(f"✅ Loaded {len(market_ids)} open Polymarket market IDs")
    return market_ids

def main():
    now_iso = datetime.utcnow().isoformat()
    ts = now_iso + "Z"

    market_ids = load_market_ids(now_iso)
    snapshots, outcomes = [], []

    for mid in market_ids:
        clob = fetch_clob(mid)
        if not clob:
            continue

        clob_outcomes = clob.get("outcomes", [])

        # Extract YES price
        yes_price = next((o.get("price") for o in clob_outcomes if o.get("name", "").lower() == "yes"), None)
        price = yes_price / 100 if yes_price is not None else None

        snapshots.append({
            "market_id":  mid,
            "price":      round(price, 4) if price is not None else None,
            "yes_bid":    None,
            "no_bid":     None,
            "volume":     None,
            "liquidity":  None,
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        for outcome in clob_outcomes:
            name = outcome.get("name")
            outcome_price = outcome.get("price")
            if name and outcome_price is not None:
                outcomes.append({
                    "market_id":    mid,
                    "outcome_name": name,
                    "price":        outcome_price / 100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket_clob",
                })

    print(f"📦 Writing {len(snapshots)} snapshots and {len(outcomes)} outcomes to Supabase…")
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)
    print("✅ Done.")

if __name__ == "__main__":
    main()
