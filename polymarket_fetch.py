# ✅ polymarket_fetch.py – top-200 Polymarket questions, YES price + $-volume

import time, requests, logging
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

GAMMA   = "https://gamma-api.polymarket.com/markets"
CLOB    = "https://clob.polymarket.com/markets/{}"
TRADES  = "https://clob.polymarket.com/markets/{}/trades"

# ───────────────── fetch helpers
def fetch_gamma(limit=500, max_pages=30):
    out, offset = [], 0
    for _ in range(max_pages):
        r = requests.get(GAMMA, params={"limit":limit,"offset":offset}, timeout=15)
        if r.status_code == 429:
            logging.warning("Gamma 429; sleep 10 s"); time.sleep(10); continue
        r.raise_for_status()
        batch = r.json() if isinstance(r.json(), list) else r.json().get("markets",[])
        if not batch: break
        out.extend(batch); offset += limit
        logging.info("fetched %s markets", len(out))
    return out

def fetch_clob(mid:str, slug:str|None):
    for ident in (mid, slug):
        if not ident: continue
        r = requests.get(CLOB.format(ident), timeout=10)
        if r.status_code == 404: continue
        r.raise_for_status(); return r.json()
    return None

def last24h_stats(mid:str):
    try:
        r = requests.get(TRADES.format(mid), timeout=10)
        if r.status_code == 404: return 0.0,0,None
        r.raise_for_status()
        cutoff = datetime.utcnow() - timedelta(hours=24)
        vol_ct=0; vol_d=0.0
        for t in r.json().get("trades", []):
            if parser.parse(t["timestamp"]) >= cutoff:
                size=t["amount"]; price=t["price"]/100
                vol_ct+=size; vol_d+=size*price
        vwap = round(vol_d/vol_ct,4) if vol_ct else None
        return round(vol_d,2), vol_ct, vwap
    except Exception as e:
        logging.warning("trade fetch failed %s: %s", mid, e)
        return 0.0,0,None

# ───────────────────────── main
def main():
    gamma_all = fetch_gamma()

    closed = {"RESOLVED","FINALIZED","SETTLED","CANCELLED"}
    now_iso= datetime.utcnow().isoformat()

    live=[]
    for g in gamma_all:
        if (g.get("status") or g.get("state") or "").upper() in closed: continue
        exp = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if exp and exp <= now_iso: continue
        g["volume24Hr"] = float(g.get("volume24Hr") or 0)
        live.append(g)

    top = sorted(live,key=lambda x:x["volume24Hr"],reverse=True)[:200]
    logging.info("selected %s live markets", len(top))

    ts = datetime.utcnow().isoformat()+"Z"
    rows_m, rows_s, rows_o = [],[],[]

    for g in top:
        mid  = g["id"]; slug=g.get("slug")
        title= g.get("title") or g.get("question") or \
               (slug.replace('-',' ').title() if slug else mid)
        exp  = g.get("endDate") or g.get("endTime") or g.get("end_time")

        # metadata
        rows_m.append({
            "market_id":mid,"market_name":title,"market_description":g.get("description") or "",
            "event_name":title,"event_ticker":slug or mid,
            "expiration":exp,"tags":g.get("categories") or [],
            "source":"polymarket","status":"TRADING"
        })

        # order book / price
        clob = fetch_clob(mid, slug)
        tokens = []
        if clob:
            tokens = (clob.get("outcomes") or clob.get("outcomeTokens") or [])
        yes_token = next((t for t in tokens if t.get("name","").lower()=="yes"), None)
        price = None
        if yes_token:
            price = yes_token.get("price")
            if price is None:
                price = yes_token.get("probability")
            if price is not None:
                price = price/100

        vol_d, vol_ct, vwap = last24h_stats(mid)

        rows_s.append({
            "market_id":mid,"price":round(price,4) if price is not None else None,
            "yes_bid":None,"no_bid":None,
            "volume":vol_ct,"dollar_volume":vol_d,"vwap":vwap,
            "liquidity":float(g.get("liquidity") or 0),
            "expiration":exp,"timestamp":ts,"source":"polymarket"
        })

        for t in tokens:
            p = t.get("price") if t.get("price") is not None else t.get("probability")
            if p is None: continue
            rows_o.append({
                "market_id":mid,"outcome_name":t["name"],
                "price":p/100,"volume":None,
                "timestamp":ts,"source":"polymarket"
            })

    # insert in FK-safe order
    insert_to_supabase("markets",rows_m)
    insert_to_supabase("market_snapshots",rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes",rows_o, conflict_key=None)
    logging.info("Inserted %s markets, %s snapshots, %s outcomes",
                 len(rows_m),len(rows_s),len(rows_o))

if __name__=="__main__":
    main()
