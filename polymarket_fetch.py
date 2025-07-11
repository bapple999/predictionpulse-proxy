# ✅ polymarket_fetch.py – fetch Polymarket markets with price + dollar volume

import os, time, requests, logging
from datetime import datetime, timedelta
from dateutil.parser import parse
from common import insert_to_supabase

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

GAMMA  = "https://gamma-api.polymarket.com/markets"
CLOB   = "https://clob.polymarket.com/markets/{}"
TRADES = "https://clob.polymarket.com/markets/{}/trades"

def fetch_gamma(limit: int = 500, max_pages: int = 30):
    out, offset = [], 0
    for _ in range(max_pages):
        r = requests.get(GAMMA, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            logging.warning("Gamma 429 – sleeping 10s")
            time.sleep(10)
            continue
        r.raise_for_status()
        batch = r.json().get("markets", []) if isinstance(r.json(), dict) else r.json()
        if not batch: break
        out.extend(batch)
        offset += limit
    logging.info("Fetched %s markets", len(out))
    return out

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
            ts = parse(t["timestamp"])
            if ts >= cutoff:
                size = t["amount"]
                price = t["price"] / 100
                vol_ct += size
                vol_d += size * price
        vwap = round(vol_d / vol_ct, 4) if vol_ct else None
        return round(vol_d, 2), vol_ct, vwap
    except Exception as e:
        logging.warning("Trade fetch failed %s: %s", mid, e)
        return 0.0, 0, None

def main():
    gamma_all = fetch_gamma()
    now = datetime.utcnow()
    now_iso = now.isoformat()

    closed = {"RESOLVED", "FINALIZED", "SETTLED", "CANCELLED"}
    live = []

    for g in gamma_all:
        status = (g.get("status") or g.get("state") or "").upper()
        exp = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if status in closed: continue
        if exp and exp <= now_iso: continue
        g["volume24Hr"] = float(g.get("volume24Hr") or 0)
        live.append(g)

    top = sorted(live, key=lambda x: x["volume24Hr"], reverse=True)
    logging.info("Selected %s live markets", len(top))

    rows_m, rows_s, rows_o = [], [], []
    ts = now.isoformat() + "Z"

    for g in top:
        mid   = g.get("id")
        slug  = g.get("slug")
        title = g.get("title") or g.get("question") or (slug or mid).replace('-', ' ').title()
        exp_raw = g.get("endDate") or g.get("endTime") or g.get("end_time")
        exp_dt = parse(exp_raw) if exp_raw else None
        exp = exp_dt.isoformat() if exp_dt else None
        status = g.get("status") or g.get("state") or "TRADING"
        tags = g.get("categories") or ["polymarket", g.get("category", "").lower()] if g.get("category") else ["polymarket"]

        # fetch orderbook (CLOB)
        clob = fetch_clob(mid, slug)
        tokens = (clob.get("outcomes") or clob.get("outcomeTokens")) if clob else []

        # price from YES token
        price = None
        yes_token = next((t for t in tokens if t.get("name", "").lower() == "yes"), None)
        if yes_token:
            price = yes_token.get("price", yes_token.get("probability"))
            if price is not None: price = price / 100

        # 24h trade stats
        vol_d, vol_ct, vwap = last24h_stats(mid)

        print(f"Inserting market {mid} — price: {price}, $vol: {vol_d}, exp: {exp}")

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
            "volume": vol_ct,
            "dollar_volume": vol_d,
            "vwap": vwap,
            "liquidity": None,
            "expiration": exp,
            "timestamp": ts,
            "source": "polymarket",
        })

        for t in tokens:
            p = t.get("price", t.get("probability"))
            if p is None: continue
            rows_o.append({
                "market_id": mid,
                "outcome_name": t.get("name"),
                "price": p / 100,
                "volume": t.get("volume"),
                "timestamp": ts,
                "source": "polymarket",
            })

    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    logging.info("Inserted %s markets, %s snapshots, %s outcomes",
                 len(rows_m), len(rows_s), len(rows_o))

if __name__ == "__main__":
    main()
