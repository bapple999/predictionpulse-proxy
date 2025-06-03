import os, requests
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

CLOB  = "https://clob.polymarket.com/markets/{}"
TRADES= "https://clob.polymarket.com/markets/{}/trades"

# ───────────────── helpers
def fetch_clob(mid: str):
    r = requests.get(CLOB.format(mid), timeout=8)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()

def trade_stats(mid:str):
    r = requests.get(TRADES.format(mid), timeout=8)
    if r.status_code == 404: return (0.0,0,None)
    r.raise_for_status()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    vol_ct=0; vol_d=0.0
    for t in r.json().get("trades", []):
        if parser.parse(t["timestamp"]) >= cutoff:
            size=t["amount"]; price=t["price"]/100
            vol_ct+=size; vol_d+=size*price
    vwap = round(vol_d/vol_ct,4) if vol_ct else None
    return round(vol_d,2), vol_ct, vwap

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

        vol_d, vol_ct, vwap = trade_stats(mid)

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
