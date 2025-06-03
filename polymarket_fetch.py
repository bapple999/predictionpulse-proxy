# ✅ polymarket_fetch.py – top 200 markets by true dollar volume + YES price

import requests, time
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase

GAMMA_ENDPOINT = "https://gamma-api.polymarket.com/markets"
CLOB_ENDPOINT  = "https://clob.polymarket.com/markets/{}"
TRADES_ENDPOINT = "https://clob.polymarket.com/markets/{}/trades"

def fetch_gamma_markets(limit=500, max_pages=30):
    print("📱 Fetching Polymarket markets (Gamma)…", flush=True)
    markets, offset, pages = [], 0, 0
    while pages < max_pages:
        r = requests.get(GAMMA_ENDPOINT, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            print("⏳ Rate‑limited; sleeping 10 s", flush=True)
            time.sleep(10)
            continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            batch = data
        else:
            batch = data.get("markets", [])
        if not batch:
            break
        markets.extend(batch)
        offset += limit
        pages += 1
        print(f"⏱  {len(batch):4} markets (offset {offset})", flush=True)
    print(f"🔍 Total markets fetched: {len(markets)}", flush=True)
    return markets

def fetch_clob(mid: str):
    r = requests.get(CLOB_ENDPOINT.format(mid), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def fetch_trade_stats(mid: str):
    try:
        r = requests.get(TRADES_ENDPOINT.format(mid), timeout=10)
        r.raise_for_status()
        trades = r.json().get("trades", [])
        cutoff = datetime.utcnow() - timedelta(hours=24)

        total_contracts = 0
        total_dollar_volume = 0.0

        for t in trades:
            ts = parser.parse(t["timestamp"])
            if ts >= cutoff:
                size = t["amount"]
                price = t["price"] / 100  # convert from cents to dollars
                total_contracts += size
                total_dollar_volume += size * price

        vwap = total_dollar_volume / total_contracts if total_contracts else None
        return round(total_dollar_volume, 2), total_contracts, round(vwap, 4) if vwap else None
    except Exception as e:
        print(f"⚠️ Trade fetch failed for Polymarket {mid}: {e}")
        return 0.0, 0, None

def main():
    gamma_all = fetch_gamma_markets()
    now_iso = datetime.utcnow().isoformat()
    ts = now_iso + "Z"

    # safer handling of volume field
    valid_markets = []
    for g in gamma_all:
        try:
            g["volume24Hr"] = float(g.get("volume24Hr") or 0)
            valid_markets.append(g)
        except:
            continue

    gamma = sorted(valid_markets, key=lambda g: g["volume24Hr"], reverse=True)[:200]
    print(f"🏆 Top 200 markets selected by volume", flush=True)

    rows_m, rows_s, rows_o = [], [], []

    for g in gamma:
        mid = g.get("id")
        title = g.get("title") or g.get("question") or ""
        end_d = g.get("endDate") or g.get("endTime") or g.get("end_time")
        if not end_d or not mid:
            continue

        clob = fetch_clob(mid)
        outcomes = clob.get("outcomes", []) if clob else []

        yes_price = next((o["price"] for o in outcomes if o.get("name", "").lower() == "yes" and o.get("price") is not None), None)
        price = yes_price / 100 if yes_price is not None else None

        dollar_volume, contract_volume, vwap = fetch_trade_stats(mid)

        rows_m.append({
            "market_id":          mid,
            "market_name":        title,
            "market_description": g.get("description"),
            "event_name":         title,
            "event_ticker":       g.get("slug") or mid,
            "expiration":         end_d,
            "tags":               g.get("categories") or [],
            "source":             "polymarket",
            "status":             g.get("status") or "TRADING",
        })

        rows_s.append({
            "market_id":   mid,
            "price":       round(price, 4) if price is not None else None,
            "yes_bid":     None,
            "no_bid":      None,
            "volume":      contract_volume,
            "dollar_volume": dollar_volume,
            "vwap":        vwap,
            "liquidity":   float(g.get("liquidity") or 0),
            "expiration":  end_d,
            "timestamp":   ts,
            "source":      "polymarket",
        })

        for o in outcomes:
            name  = o.get("name")
            outcome_price = o.get("price")
            if name and outcome_price is not None:
                rows_o.append({
                    "market_id":    mid,
                    "outcome_name": name,
                    "price":        outcome_price / 100,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "polymarket",
                })

    print(f"📦 Inserting {len(rows_m)} markets, {len(rows_s)} snapshots, {len(rows_o)} outcomes", flush=True)

    if rows_m:
        insert_to_supabase("markets", rows_m)
    else:
        print("⚠️  no data for markets")

    if rows_s:
        insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    else:
        print("⚠️  no data for market_snapshots")

    if rows_o:
        insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    else:
        print("⚠️  no data for market_outcomes")

    print("✅ Done.", flush=True)

if __name__ == "__main__":
    main()
