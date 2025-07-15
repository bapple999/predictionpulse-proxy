import os
import requests
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase, fetch_stats_concurrent

# refresh prices for the most active Kalshi markets (24h volume)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

# include the Kalshi API token for authenticated requests
HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}",
    "Content-Type": "application/json",
}

MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
TRADES_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets/{}/trades"

def fetch_all_markets(limit=1000):
    markets, seen, offset = [], set(), 0
    while True:
        resp = requests.get(
            MARKETS_URL,
            params={"limit": limit, "offset": offset},
            headers=HEADERS_KALSHI,
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json().get("markets", [])
        if not batch:
            break
        tickers = [m.get("ticker") for m in batch if m.get("ticker")]
        if any(t in seen for t in tickers):
            break
        seen.update(tickers)
        markets.extend(batch)
        offset += limit
        if len(batch) < limit:
            break
    return markets

def fetch_known_market_ids(limit: int = 10000) -> set[str]:
    """Return a set of market IDs already present in Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id&limit={limit}"
    ids, offset = set(), 0
    while True:
        resp = requests.get(
            f"{url}&offset={offset}",
            headers=SUPA_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        ids.update(m.get("market_id") for m in batch if m.get("market_id"))
        if len(batch) < limit:
            break
        offset += limit
    return ids

def fetch_trade_stats(ticker: str):
    try:
        r = requests.get(
            TRADES_ENDPOINT.format(ticker),
            headers=HEADERS_KALSHI,
            timeout=10,
        )
        if r.status_code == 404:
            return 0.0, 0, None
        r.raise_for_status()
        trades = r.json().get("trades", [])
        cutoff = datetime.utcnow() - timedelta(hours=24)

        total_contracts = 0
        total_dollar_volume = 0.0

        for t in trades:
            ts = parser.parse(t["timestamp"])
            if ts >= cutoff:
                size = t["size"]
                price = t["price"]
                total_contracts += size
                total_dollar_volume += size * price

        vwap = total_dollar_volume / total_contracts if total_contracts else None
        return round(total_dollar_volume, 2), total_contracts, round(vwap, 4) if vwap else None
    except Exception as e:
        print(f"⚠️ Trade fetch failed for Kalshi {ticker}: {e}")
        return 0.0, 0, None

def main():
    ts = datetime.utcnow().isoformat() + "Z"
    markets = fetch_all_markets()

    # fetch 24h trade stats for ranking concurrently
    tickers = [m.get("ticker") for m in markets if m.get("ticker")]
    stats_list, failed = fetch_stats_concurrent(tickers, fetch_trade_stats)
    stats_map = {mid: stats for mid, stats in stats_list}
    for m in markets:
        tkr = m.get("ticker")
        if not tkr:
            continue
        dv, ct, vw = stats_map.get(tkr, (0.0, 0, None))
        m["volume_24h"] = ct
        m["dollar_volume_24h"] = dv
        m["vwap_24h"] = vw
    if failed:
        print("⚠️ Failed trade stats for:", failed)

    # rank by past 24h volume
    top_markets = sorted(
        [m for m in markets if m.get("ticker")],
        key=lambda m: m.get("volume_24h", 0),
        reverse=True
    )[:200]

    # only insert snapshots for markets already present in the DB to avoid
    # foreign‑key errors
    known_ids = fetch_known_market_ids()

    snapshots, outcomes = [] , []

    skipped = 0
    for m in top_markets:
        mid = m["ticker"]
        if mid not in known_ids:
            skipped += 1
            continue
        last_price = m.get("last_price")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")

        contract_volume = m.get("volume_24h", 0)
        dollar_volume   = m.get("dollar_volume_24h", 0.0)
        vwap            = m.get("vwap_24h")

        snapshots.append({
            "market_id":  mid,
            "price":      round(last_price, 4) if last_price is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     contract_volume,
            "dollar_volume": dollar_volume,
            "vwap":       vwap,
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi",
        })

        if last_price is not None:
            outcomes.append({
                "market_id":    mid,
                "outcome_name": m.get("title") or mid,
                "price":        last_price,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi",
            })

    print(f"📦 Writing {len(snapshots)} snapshots and {len(outcomes)} outcomes to Supabase…")
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)
    if skipped:
        print(f"Skipped {skipped} unknown markets")
    print("✅ Done.")

if __name__ == "__main__":
    main()
