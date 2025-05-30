import os
import requests
from datetime import datetime, timedelta
from dateutil import parser
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
TRADES_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets/{}/trades"

def fetch_all_markets(limit=1000):
    markets, seen, offset = [], set(), 0
    while True:
        resp = requests.get(MARKETS_URL, params={"limit": limit, "offset": offset}, timeout=20)
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

def fetch_trade_stats(ticker: str):
    try:
        r = requests.get(TRADES_ENDPOINT.format(ticker), timeout=10)
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

    top_markets = sorted(
        [m for m in markets if isinstance(m.get("volume"), (int, float))],
        key=lambda m: m["volume"],
        reverse=True
    )[:200]

    snapshots, outcomes = [] , []

    for m in top_markets:
        mid = m["ticker"]
        last_price = m.get("last_price")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")

        dollar_volume, contract_volume, vwap = fetch_trade_stats(mid)

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
    print("✅ Done.")

if __name__ == "__main__":
    main()
