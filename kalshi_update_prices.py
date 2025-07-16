import os
import time
import logging
import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser
from common import insert_to_supabase, fetch_stats_concurrent

# refresh prices for the most active Kalshi markets (24h volume)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "100"))
SUPA_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# include the Kalshi API token for authenticated requests
HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}",
    "Content-Type": "application/json",
}

MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
TRADES_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets/{}/trades"

# only refresh markets expiring within this window
UPDATE_WINDOW_DAYS = 7


def request_json(url: str, headers=None, params=None, tries: int = 3, backoff: float = 1.5):
    """GET *url* and return JSON with simple retries."""
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning("request failed (%s/%s) %s: %s", i + 1, tries, url, e)
            if i == tries - 1:
                return None
            time.sleep(backoff * (2**i))

def fetch_all_markets(limit=1000):
    markets, seen, offset = [], set(), 0
    while True:
        j = request_json(
            MARKETS_URL,
            headers=HEADERS_KALSHI,
            params={"limit": limit, "offset": offset},
        )
        if j is None:
            break
        batch = j.get("markets", [])
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

def fetch_active_market_info(days: int = UPDATE_WINDOW_DAYS) -> dict[str, datetime | None]:
    """Return mapping of market_id to expiration for active markets."""
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration&source=eq.kalshi"
    rows = request_json(url, headers=SUPA_HEADERS) or []
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=days)
    info: dict[str, datetime | None] = {}
    for r in rows:
        mid = r.get("market_id")
        exp_raw = r.get("expiration")
        exp_dt = parser.isoparse(exp_raw) if exp_raw else None
        if exp_dt is None or (now <= exp_dt <= future):
            info[mid] = exp_dt
    return info

def fetch_trade_stats(ticker: str):
    try:
        j = request_json(TRADES_ENDPOINT.format(ticker), headers=HEADERS_KALSHI)
        if j is None:
            return 0.0, 0, None
        trades = j.get("trades", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

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
        logging.warning("trade fetch failed for %s: %s", ticker, e)
        return 0.0, 0, None

def main():
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    markets = fetch_all_markets()

    active = fetch_active_market_info()
    logging.info("loaded %s active market ids", len(active))

    tickers = [m.get("ticker") for m in markets if m.get("ticker") in active]
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
        logging.warning("failed trade stats for %s", failed)

    # rank by past 24h volume but only include known/active markets
    top_markets = sorted(
        [m for m in markets if m.get("ticker") in active],
        key=lambda m: m.get("volume_24h", 0),
        reverse=True,
    )[:FETCH_LIMIT]

    # only insert snapshots for markets already present in the DB
    known_ids = set(active.keys())

    snapshots, outcomes = [] , []
    skipped = 0
    for m in top_markets:
        mid = m.get("ticker")
        if not mid:
            logging.info("skipping market without ticker")
            skipped += 1
            continue
        if mid not in known_ids:
            logging.info("skipping unknown market %s", mid)
            skipped += 1
            continue

        exp_raw = m.get("close_time") or m.get("closeTime") or m.get("expiration")
        exp_dt = parser.parse(exp_raw) if exp_raw else active.get(mid)
        if exp_dt:
            if exp_dt <= now:
                logging.info("skipping %s: expired", mid)
                skipped += 1
                continue
            if exp_dt - now > timedelta(days=UPDATE_WINDOW_DAYS):
                logging.info("skipping %s: expires beyond window", mid)
                skipped += 1
                continue

        last_price = m.get("last_price")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        if last_price is None and yes_bid is None and no_bid is None:
            logging.info("skipping %s: no price data", mid)
            skipped += 1
            continue

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

    logging.info("writing %s snapshots and %s outcomes", len(snapshots), len(outcomes))
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes", outcomes, conflict_key=None)
    if skipped:
        logging.info("skipped %s markets", skipped)
    logging.info("done")

if __name__ == "__main__":
    main()
