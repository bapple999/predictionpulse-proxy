# polymarket_update_prices.py – 5 min snapshot updater for Polymarket
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

# Fetch full CLOB for a market

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def load_market_ids(now_iso: str):
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration"
    resp = requests.get(url, headers=SUPA_HEADERS, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    filtered = [r["market_id"] for r in rows if r.get("expiration") is not None and r["expiration"] > now_iso]
    skipped = len(rows) - len(filtered)
    if skipped:
        print(f"⚠️ Skipped {skipped} rows with null expiration")
    return filtered

def main():
    ts = datetime.utcnow().isoformat() + "Z"
    now_iso = datetime.utcnow().isoformat()

    market_ids = load_market_ids(now_iso)
    print(f"📊 Loaded {len(market_ids)} active markets", flush=True)

    snapshots, outcomes = [], []

    for mid in market_ids:
        clob = fetch_clob(mid)
        if not clob:
            continue

        clob_outcomes = clob.get("outcomes", [])

        # Estimate midpoint probability if binary market
        if len(clob_outcomes) == 2 and all(o.get("price") is not None for o in clob_outcomes):
            yes_price = clob_outcomes[0]["price"]
            no_price = clob_outcomes[1]["price"]
            prob = (yes_price/100 + (1 - no_price/100)) / 2
        else:
            prob = None

        snapshots.append({
            "market_id": mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    None,
            "no_bid":     None,
            "volume":     None,
            "liquidity":  None,
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # Insert all outcomes from clob
        for outcome in clob_outcomes:
            outcomes.append({
                "market_id":    mid,
                "outcome_name": outcome.get("name"),
                "price":        outcome.get("price") / 100 if outcome.get("price") is not None else None,
                "volume":       None,
                "timestamp":    ts,
                "source":       "polymarket_clob",
            })

    print("💾 Writing snapshots to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    print("💾 Writing outcomes to Supabase…", flush=True)
    insert_to_supabase("market_outcomes",  outcomes, conflict_key=None)
    print(f"✅ Snapshots {len(snapshots)} | Outcomes {len(outcomes)}", flush=True)

if __name__ == "__main__":
    main()
