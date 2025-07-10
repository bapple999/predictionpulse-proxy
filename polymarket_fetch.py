# ✅ polymarket_fetch.py – full Polymarket market list with YES price + $-volume

import os, time, requests, logging
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.parser import parse
from common import insert_to_supabase

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

GAMMA  = "https://gamma-api.polymarket.com/markets"
CLOB   = "https://clob.polymarket.com/markets/{}"
TRADES = "https://clob.polymarket.com/markets/{}/trades"

# ───────────────── fetch helpers
def fetch_gamma(limit=1000):
    r = requests.get(f"https://gamma.polymarket.com/markets?limit={limit}")
    r.raise_for_status()
    markets = r.json().get("markets") if isinstance(r.json(), dict) else r.json()
    logging.info("Fetched %s Polymarket markets", len(markets))
    return markets

def fetch_clob(mid: str, slug: str | None):
    for ident in (mid, slug):
        if not ident: continue
        r = requests.get(CLOB.format(ident), timeout=10)
        if r.status_code == 404: continue
        r.raise_for_status(); return r.json()
    return None

def last24h_stats(mid: str):
    try:
        r = requests.get(TRADES.format(mid), timeout=10)
        if r.status_code == 404: return 0.0, 0, None
        r.raise_for_status()
        cutoff = datetime.utcnow() - timedelta(hours=24)
        vol_ct = vol_d = 0
        for t in r.json().get("trades", []):
            if parser.parse(t["timestamp"]) >= cutoff:
                size = t["amount"]; price = t["price"] / 100
                vol_ct += size; vol_d += size * price
        vwap = round(vol_d / vol_ct, 4) if vol_ct else None
        return round(vol_d, 2), vol_ct, vwap
    except Exception as e:
        logging.warning("trade fetch failed %s: %s", mid, e)
        return 0.0, 0, None

# ───────────────────────── main
def main():
    gamma_all = fetch_gamma()

    closed = {"RESOLVED", "FINALIZED", "SETTLED", "CANCELLED"}
    now_iso = datetime.utcnow().isoformat()

    live = []
    for g in gamma_all:
        if (g.get("status") or g.get("state") or "").upper() in closed:
            continue
        exp = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if exp and exp <= now_iso:
            continue
        g["volume24Hr"] = float(g.get("volume24Hr") or 0)
        live.append(g)

    top = sorted(live, key=lambda x: x["volume24Hr"], reverse=True)
    logging.info("selected %s live markets", len(top))

    rows_m, rows_s, rows_o = [], [], []

    for g in top:
        mid  = g.get("slug") or g.get("id")
        title = g.get("title") or g.get("question") or (
                mid.replace('-', ' ').title() if mid else "")
        exp_dt = parse(g["endDate"]) if g.get("endDate") else None
        exp    = exp_dt.isoformat() if exp_dt else None
        status = g.get("status") or g.get("state") or "TRADING"
        tags   = g.get("categories")
        if not tags:
            if g.get("category"):
                tags = ["polymarket", g["category"].lower()]
            else:
                tags = ["polymarket"]
        outcomes = g.get("outcomes") or []
        price = None
        volume = 0.0
        for o in outcomes:
            p = o.get("probability") if o.get("probability") is not None else o.get("price")
            if p is not None:
                p = p / 100 if p > 1 else p
                if price is None or p > price:
                    price = p
            volume += float(o.get("volume") or 0)
        ts = datetime.utcnow().isoformat() + "Z"
        print(f"Inserting market {mid} with expiration {exp}, status {status}, price {price}")

        # ── metadata
        rows_m.append({
            "market_id": mid,
            "market_name": title,
            "market_description": g.get("description") or "",
            "event_name": title,
            "event_ticker": mid,
            "expiration": exp,
            "tags": tags,
            "source": "polymarket",
            "status": status,
        })

        rows_s.append({
            "market_id": mid,
            "price": round(price, 4) if price is not None else None,
            "yes_bid": None,
            "no_bid": None,
            "volume": volume,
            "dollar_volume": None,
            "vwap": None,
            "liquidity": None,
            "expiration": exp,
            "timestamp": ts,
            "source": "polymarket",
        })

        # ── outcomes
        for t in outcomes:
            p = t.get("probability") if t.get("probability") is not None else t.get("price")
            if p is None:
                continue
            p = p / 100 if p > 1 else p
            rows_o.append({
                "market_id": mid,
                "outcome_name": t.get("title") or t.get("name"),
                "price": p,
                "volume": t.get("volume"),
                "timestamp": ts,
                "source": "polymarket",
            })

    # ── insert in FK-safe order
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    logging.info("Inserted %s markets, %s snapshots, %s outcomes",
                 len(rows_m), len(rows_s), len(rows_o))
    print(f"Inserted {len(rows_m)} markets and {len(rows_o)} outcomes")

    # diagnostics: fetch sample rows
    diag_url = f"{os.environ['SUPABASE_URL']}/rest/v1/latest_snapshots?select=market_id,source,price&order=timestamp.desc&limit=3"
    r = requests.get(diag_url, headers={
        'apikey': os.environ['SUPABASE_SERVICE_ROLE_KEY'],
        'Authorization': f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}"
    })
    if r.status_code == 200:
        logging.info("Latest snapshots sample: %s", r.json())
    else:
        logging.warning("Diagnostics fetch failed %s: %s", r.status_code, r.text[:150])

if __name__ == "__main__":
    main()
