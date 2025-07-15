import os, requests
from datetime import datetime, timedelta
from dateutil import parser
from common import (
    insert_to_supabase,
    fetch_clob,
    last24h_stats,
    CLOB_URL,
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

TRADES = os.environ.get(
    "POLYMARKET_TRADES_URL", "https://clob.polymarket.com/markets/{}/trades"
)

# ───────────────── helpers
# `fetch_clob` and `last24h_stats` are imported from ``common`` so that they
# respect any environment-based overrides for Polymarket endpoints.

def load_market_ids():
    # include markets with NULL expiration as well
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id"
    r = requests.get(url, headers=SUPA_HEADERS, timeout=10); r.raise_for_status()
    return [row["market_id"] for row in r.json()]

# ───────────────── main
def main():
    ts = datetime.utcnow().isoformat() + "Z"
    ids = load_market_ids()
    print(f"↻ refreshing {len(ids)} polymarket prices…")

    snapshots, outcomes = [], []

    for mid in ids:
        clob = fetch_clob(mid)
        if not clob:                 # market may be expired or delisted
            continue

        toks = (clob.get("outcomes") or clob.get("outcomeTokens") or [])
        yes_tok = next((t for t in toks if t.get("name","").lower()=="yes"), None)
        price = None
        if yes_tok:
            price = yes_tok.get("price")
            if price is None:
                price = yes_tok.get("probability")
            if price is not None:
                price = price/100

        vol_d, vol_ct, vwap = last24h_stats(mid)

        snapshots.append({
            "market_id":mid,
            "price":round(price,4) if price is not None else None,
            "yes_bid":None,"no_bid":None,
            "volume":vol_ct,"dollar_volume":vol_d,"vwap":vwap,
            "liquidity":None,"timestamp":ts,"source":"polymarket_clob"
        })

        for t in toks:
            p = t.get("price") if t.get("price") is not None else t.get("probability")
            if p is None: continue
            outcomes.append({
                "market_id":mid,"outcome_name":t["name"],
                "price":p/100,"volume":None,
                "timestamp":ts,"source":"polymarket_clob"
            })

    print(f"📦 writing {len(snapshots)} snapshots • {len(outcomes)} outcomes")
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes",  outcomes,  conflict_key=None)
    print("✅ done")

if __name__ == "__main__":
    from datetime import datetime
    main()
