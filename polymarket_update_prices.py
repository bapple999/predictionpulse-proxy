# ✅ polymarket_update_prices.py – lightweight updater using YES price as market price

import os
import requests
from datetime import datetime
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

CLOB_ENDPOINT = "https://clob.polymarket.com/markets/{}"

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def load_market_ids(now_iso: str):
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration,volume&order=volume.desc&limit=200"
    resp = requests.get(url, headers=SUPA_HEADERS, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    return [r["market_id"] for r in rows if r.get("expiration") and r["expiration"] > now_iso]

def main():
    ts = datetime.utcnow().isoformat() + "Z"
    now_iso = datetime.utcnow().isoformat()

    market_ids = load_market_ids(now_iso)
    snapshots, outcomes = [], []

    for mid in market_ids:
        clob = fetch_clob(mid)
        if not clob:
            continue

        clob_outcomes = clob.get("outcomes", [])

        if len(clob_outcomes) == 2 and all(o.get("price") is not None for o in clob_outcomes):
            yes_price = clob_outcomes[0]["price"]
            price = yes_price / 100
        else:
            price = None

        snapshots.append({
            "market_id": mid,
            "price":      round(price, 4) if price is not None else None,
            "yes_bid":    None,
            "no_bid":     None,
            "volume":     None,
            "liquidity":  None,
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        for outcome in clob_outcomes:
            outcomes.append({
                "market_id":    mid,
                "outcome_name": outcome.get("name"),
                "price":        outcome.get("price") / 100 if outcome.get("price") is not None else None,
                "volume":       None,
                "timestamp":    ts,
                "source":       "polymarket_clob",
            })

    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)

if __name__ == "__main__":
    main()
