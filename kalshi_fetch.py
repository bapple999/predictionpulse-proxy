# ✅ kalshi_fetch.py – fetch all Kalshi markets using pagination

import os, requests
from datetime import datetime, timedelta
from dateutil.parser import parse
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}",
    "Content-Type":  "application/json",
}
EVENTS_URL   = "https://api.elections.kalshi.com/trade-api/v2/events"
MARKETS_URL  = "https://api.elections.kalshi.com/trade-api/v2/markets"
TRADES_URL   = "https://api.elections.kalshi.com/trade-api/v2/markets/{}/trades"

# ---------- helpers ----------
def fetch_events():
    j = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15).json()
    return {e["ticker"]: e for e in j.get("events", []) if e.get("ticker")}

def fetch_all_markets(limit=1000):
    markets, cursor = [], None
    while True:
        params = {"limit": limit, **({"cursor": cursor} if cursor else {})}
        j = requests.get(MARKETS_URL, headers=HEADERS_KALSHI, params=params, timeout=20).json()
        batch, cursor = j.get("markets", []), j.get("cursor")
        if not batch: break
        markets.extend(batch)
        if not cursor: break
    return markets

def fetch_trade_stats(tkr: str):
    try:
        r = requests.get(TRADES_URL.format(tkr), headers=HEADERS_KALSHI, timeout=10)
        if r.status_code == 404:  # no trades yet
            return 0.0, 0, None
        r.raise_for_status()
        trades = r.json().get("trades", [])
        cutoff = datetime.utcnow() - timedelta(hours=24)

        dollar_volume, vol_ct = 0.0, 0
        for t in trades:
            if parse(t["timestamp"]) >= cutoff:
                vol_ct += t["size"]
                dollar_volume += t["size"] * t["price"]

        vwap = dollar_volume / vol_ct if vol_ct else None
        return round(dollar_volume, 2), vol_ct, round(vwap, 4) if vwap else None
    except Exception as e:
        print(f"⚠️ Trade fetch failed for {tkr}: {e}")
        return 0.0, 0, None

# ---------- main ----------
def main():
    events = fetch_events()
    raw    = fetch_all_markets()
    print(f"Fetched {len(raw)} Kalshi markets")

    # keep only actively trading markets, fetch 24h stats for ranking
    active = [m for m in raw if (m.get("status", "TRADING")).upper() == "TRADING"]
    for m in active:
        dv, ct, vw = fetch_trade_stats(m["ticker"])
        m["volume_24h"] = ct
        m["dollar_volume_24h"] = dv
        m["vwap_24h"] = vw

    # sort by past 24h volume
    active = sorted(active, key=lambda m: m.get("volume_24h", 0), reverse=True)

    ts = datetime.utcnow().isoformat()+"Z"
    rows_m, rows_s, rows_o = [], [], []

    for m in active:
        tkr      = m["ticker"]
        event    = events.get(m.get("event_ticker")) or {}
        last_px  = m.get("last_price")
        yes_bid  = m.get("yes_bid")
        no_bid   = m.get("no_bid")
        vol_ct   = m.get("volume") or 0
        liquidity= m.get("open_interest") or 0
        exp_dt   = parse(m["close_time"]) if m.get("close_time") else None
        expiration = exp_dt.isoformat() if exp_dt else None
        status    = m.get("status") or "TRADING"
        tags      = [tkr.split("/")[0]] if m.get("ticker") else ["kalshi"]
        event_name = m.get("ticker") or m.get("event_ticker")

        # --- dollar vol / VWAP ---
        confirmed_ct = m.get("volume_24h", 0)
        dollar_volume = m.get("dollar_volume_24h", 0.0)
        vwap = m.get("vwap_24h")
        if confirmed_ct == 0 and last_px is not None:
            dollar_volume = round(last_px * vol_ct, 2)   # fallback approximation

        print(f"Inserting market {tkr} with expiration {expiration}, status {status}, price {last_px}")

        # ---------- markets ----------
        rows_m.append({
            "market_id":          tkr,
            "market_name":        m.get("title") or m.get("description") or tkr,
            "market_description": m.get("description") or "",
            "event_name":         event_name,
            "event_ticker":       m.get("event_ticker") or "",
            "expiration":         expiration,
            "tags":               tags,
            "source":             "kalshi",
            "status":             status,
        })

        # ---------- snapshot ----------
        rows_s.append({
            "market_id":     tkr,
            "price":         round(last_px,4) if last_px is not None else None,
            "yes_bid":       yes_bid,
            "no_bid":        no_bid,
            "volume":        confirmed_ct or vol_ct,
            "dollar_volume": dollar_volume,
            "vwap":          vwap,
            "liquidity":     liquidity,
            "expiration":    expiration,
            "timestamp":     ts,
            "source":        "kalshi",
        })

        # ---------- outcome (YES) ----------
        rows_o.append({
            "market_id":     tkr,
            "outcome_name":  "Yes",
            "price":         last_px,
            "volume":        vol_ct,
            "timestamp":     ts,
            "source":        "kalshi",
        })

    # insert in FK-safe order
    insert_to_supabase("markets",          rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes",  rows_o, conflict_key=None)
    print(f"✅ Inserted {len(rows_m)} markets, {len(rows_s)} snapshots, {len(rows_o)} outcomes")

    # diagnostic: show last few rows from Supabase
    diag_url = f"{SUPABASE_URL}/rest/v1/latest_snapshots?select=market_id,source,price&order=timestamp.desc&limit=3"
    r = requests.get(diag_url, headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}"
    })
    if r.status_code == 200:
        print("Latest snapshots sample:", r.json())
    else:
        print("⚠️ Diagnostics fetch failed", r.status_code, r.text[:150])

if __name__ == "__main__":
    main()
