# ✅ polymarket_fetch.py – top 200 markets by true $-volume + YES price

import os, time, requests
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase

GAMMA_ENDPOINT   = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT    = "https://clob.polymarket.com/markets/{}"
TRADES_ENDPOINT  = "https://clob.polymarket.com/markets/{}/trades"

# ────────────────────────────────────────────────────────────── helpers
def fetch_gamma_markets(limit=500, max_pages=30):
    print("📱 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT,
                         params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            print("⏳ Rate-limited; sleeping 10 s", flush=True)
            time.sleep(10); continue
        r.raise_for_status()
        data  = r.json()
        batch = data if isinstance(data, list) else data.get("markets", [])
        if not batch: break
        markets.extend(batch)
        offset += limit; pages += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()

def fetch_trade_stats(mid: str):
    try:
        r = requests.get(TRADES_ENDPOINT.format(mid), timeout=10)
        if r.status_code == 404:
            return 0.0, 0, None
        r.raise_for_status()
        trades = r.json().get("trades", [])
        cutoff = datetime.utcnow() - timedelta(hours=24)
        vol_ct, vol_$ = 0, 0.0
        for t in trades:
            if parser.parse(t["timestamp"]) >= cutoff:
                size   = t["amount"]
                price$ = t["price"] / 100
                vol_ct += size
                vol_$  += size * price$
        vwap = round(vol_$/vol_ct, 4) if vol_ct else None
        return round(vol_$, 2), vol_ct, vwap
    except Exception as e:
        print(f"⚠️ Trade fetch failed for {mid}: {e}")
        return 0.0, 0, None

# ────────────────────────────────────────────────────────────── main
def main():
    gamma_all = fetch_gamma_markets()

    # 1) keep only markets that are still live
    closed   = {"RESOLVED", "FINALIZED", "SETTLED", "CANCELLED"}
    now_iso  = datetime.utcnow().isoformat()
    live     = []
    for g in gamma_all:
        status = (g.get("status") or g.get("state") or "").upper()
        if status in closed: continue
        # accept missing endDate; if present must be in future
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if end_d and end_d <= now_iso: continue
        try:
            g["volume24Hr"] = float(g.get("volume24Hr") or 0)
        except: g["volume24Hr"] = 0.0
        live.append(g)

    # 2) top 200 by 24-h contract volume
    gamma = sorted(live, key=lambda x: x["volume24Hr"], reverse=True)[:200]
    print(f"🏆 Selected {len(gamma)} open markets (top by volume)", flush=True)

    ts   = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for g in gamma:
        mid   = g["id"]
        title = g.get("title") or g.get("question") or \
                g.get("slug","").replace('-',' ').title() or mid
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")

        # ---------- always insert metadata ----------
        rows_m.append({
            "market_id":          mid,
            "market_name":        title,
            "market_description": g.get("description") or "",
            "event_name":         title,
            "event_ticker":       g.get("slug") or mid,
            "expiration":         end_d,          # may be NULL
            "tags":               g.get("categories") or [],
            "source":             "polymarket",
            "status":             "TRADING",
        })

        # ---------- snapshot & outcomes only if CLOB exists ----------
        clob = fetch_clob(mid)
        if not clob: continue                      # no orderbook yet

        outcomes   = clob.get("outcomes", [])
        yes_price¢ = next((o["price"] for o in outcomes
                           if o.get("name","").lower()=="yes" and o.get("price") is not None), None)
        price = yes_price¢/100 if yes_price¢ is not None else None

        vol$, vol_ct, vwap = fetch_trade_stats(mid)

        rows_s.append({
            "market_id":     mid,
            "price":         round(price,4) if price else None,
            "yes_bid":       None,
            "no_bid":        None,
            "volume":        vol_ct,
            "dollar_volume": vol$,
            "vwap":          vwap,
            "liquidity":     float(g.get("liquidity") or 0),
            "expiration":    end_d,
            "timestamp":     ts,
            "source":        "polymarket",
        })

        for o in outcomes:
            if o.get("price") is None: continue
            rows_o.append({
                "market_id":    mid,
                "outcome_name": o["name"],
                "price":        o["price"]/100,
                "volume":       None,
                "timestamp":    ts,
                "source":       "polymarket",
            })

    # ───────────────── insert in FK-safe order
    insert_to_supabase("markets",          rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes",  rows_o, conflict_key=None)
    print(f"✅ Inserted {len(rows_m)} markets, {len(rows_s)} snapshots, {len(rows_o)} outcomes", flush=True)

if __name__ == "__main__":
    main()

