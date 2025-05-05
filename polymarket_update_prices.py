# polymarket_update_prices.py  – 5 min snapshot/updater for Polymarket
import os
import requests
from datetime import datetime
from common import insert_to_supabase   # shared helper

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"

# ───────── helpers ───────────
def clob_prices(clob: dict):
    """Return (yesPrice, noPrice) in cents, or (None,None)."""
    if "yesPrice" in clob and "noPrice" in clob:
        return clob["yesPrice"], clob["noPrice"]
    # fallback: scan outcomes array
    outs = {o.get("name"): o.get("price") for o in clob.get("outcomes", [])}
    return outs.get("Yes"), outs.get("No")

def fetch_clob(mid: str):
    """Fetch CLOB data or return None if not on CLOB."""
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def load_market_ids(now_iso: str) -> list[str]:
    """Load all unexpired market_ids from Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration"
    resp = requests.get(url, headers=SUPA_HEADERS, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    # keep only those not expired
    return [r["market_id"] for r in rows if r.get("expiration", "") > now_iso]

# ───────── main routine ───────
def main():
    ts      = datetime.utcnow().isoformat() + "Z"
    now_iso = datetime.utcnow().isoformat()

    # 1) grab all the markets we previously ingested
    market_ids = load_market_ids(now_iso)
    print(f"🗄️  Loaded {len(market_ids)} markets from Supabase", flush=True)

    snapshots, outcomes = [], []

    for mid in market_ids:
        # 2) fetch CLOB for fresh prices
        clob = fetch_clob(mid)
        yes, no = (None, None)
        if clob:
            yes, no = clob_prices(clob)

        # 3) compute implied probability
        prob = (
            (yes/100 + (1 - no/100)) / 2
            if yes is not None and no is not None
            else None
        )

        # 4) always write a snapshot row
        snapshots.append({
            "market_id": mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes/100 if yes is not None else None,
            "no_bid":     no/100  if no  is not None else None,
            "volume":     None,      # static or fetched elsewhere
            "liquidity":  None,
            "timestamp":  ts,
            "source":     "polymarket_clob",
        })

        # 5) write outcomes when we have real prices
        if yes is not None and no is not None:
            outcomes.extend([
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

    # 6) push updates to Supabase
    print("💾 Writing snapshots to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    print("💾 Writing outcomes to Supabase…", flush=True)
    insert_to_supabase("market_outcomes",  outcomes, conflict_key=None)
    print(f"✅ Snapshots {len(snapshots)} | Outcomes {len(outcomes)}", flush=True)

if __name__ == "__main__":
    main()
