# ✅ kalshi_fetch.py – fetch all Kalshi markets using pagination

import os
import requests
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

KALSHI_API_KEY = os.environ.get("KALSHI_API_KEY")
if not KALSHI_API_KEY:
    raise RuntimeError("KALSHI_API_KEY must be set")

HEADERS_KALSHI = {
    "Authorization": f"Bearer {KALSHI_API_KEY}",
    "Content-Type":  "application/json",
}

# Allow overriding the Kalshi endpoints so a proxy can be used when direct
# network access is restricted.
EVENTS_URL  = os.environ.get(
    "KALSHI_EVENTS_URL",
    "https://api.elections.kalshi.com/trade-api/v2/events",
)
MARKETS_URL = os.environ.get(
    "KALSHI_MARKETS_URL",
    "https://api.elections.kalshi.com/trade-api/v2/markets",
)
TRADES_URL  = os.environ.get(
    "KALSHI_TRADES_URL",
    "https://api.elections.kalshi.com/trade-api/v2/markets/{}/trades",
)

# Minimum dollar volume for a market to be considered "high volume"
MIN_DOLLAR_VOLUME = 5000

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
        if r.status_code == 404:
            return None, 0, None
        r.raise_for_status()
        trades = r.json().get("trades", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        dollar_volume, vol_ct = 0.0, 0
        for t in trades:
            ts = parse(t["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            if ts >= cutoff:
                vol_ct += t["size"]
                dollar_volume += t["size"] * t["price"]

        vwap = dollar_volume / vol_ct if vol_ct else None
        return round(dollar_volume, 2), vol_ct, round(vwap, 4) if vwap else None
    except Exception as e:
        print(f"⚠️ Trade fetch failed for {tkr}: {e}")
        return None, 0, None

# ---------- main ----------
def main():
    events = fetch_events()
    raw = fetch_all_markets()
    print(f"Fetched {len(raw)} Kalshi markets")

    now = datetime.now(timezone.utc)
    kept = []
    skipped = 0
    for m in raw:
        ticker = m.get("ticker")
        if not ticker:
            print("Skipping market without ticker")
            skipped += 1
            continue

        status = (m.get("status", "TRADING")).upper()
        exp_raw = m.get("close_time") or m.get("closeTime") or m.get("expiration")
        exp_dt = parse(exp_raw) if exp_raw else None
        if exp_dt:
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            else:
                exp_dt = exp_dt.astimezone(timezone.utc)
        is_active = status == "TRADING" and (not exp_dt or exp_dt > now)

        dv, ct, vw = fetch_trade_stats(ticker)
        if dv is None:
            # volume unavailable -> skip filtering
            is_high_vol = True
        else:
            is_high_vol = dv >= MIN_DOLLAR_VOLUME

        if not (is_active or is_high_vol):
            reason = []
            if not is_active:
                reason.append("inactive")
            if not is_high_vol:
                reason.append(f"volume ${dv}")
            print(f"Skipping {ticker}: {'; '.join(reason)}")
            skipped += 1
            continue

        m["volume_24h"] = ct
        m["dollar_volume_24h"] = dv
        m["vwap_24h"] = vw
        m["_expiration"] = exp_dt
        kept.append(m)

    # ✅ unified logic: sort by dollar volume descending
    # some markets may lack a volume stat; treat `None` as zero
    kept = sorted(kept, key=lambda m: m.get("dollar_volume_24h") or 0, reverse=True)

    print(f"Filtered down to {len(kept)} markets (skipped {skipped})")

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows_m, rows_s, rows_o = [], [], []

    for m in kept:
        tkr = m["ticker"]
        event    = events.get(m.get("event_ticker")) or {}
        last_px  = m.get("last_price")
        yes_bid  = m.get("yes_bid")
        no_bid   = m.get("no_bid")
        vol_total = m.get("volume") or 0
        liquidity = m.get("open_interest") or 0
        exp_dt = m.get("_expiration")
        expiration = (
            exp_dt.isoformat().replace("+00:00", "Z") if exp_dt else None
        )
        status = m.get("status") or "TRADING"
        tags = [tkr.split("/")[0]] if m.get("ticker") else ["kalshi"]
        event_name = m.get("ticker") or m.get("event_ticker")

        confirmed_ct = m.get("volume_24h", 0)
        dollar_volume = m.get("dollar_volume_24h", 0.0)
        vwap = m.get("vwap_24h")
        if dollar_volume == 0 and last_px is not None:
            dollar_volume = round(last_px * confirmed_ct, 2)

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
            "volume":        confirmed_ct or vol_total,
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
            "volume":        vol_total,
            "timestamp":     ts,
            "source":        "kalshi",
        })

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

