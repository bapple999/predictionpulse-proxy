import os
import logging
from datetime import datetime, timedelta, timezone
from dateutil import parser
from common import insert_to_supabase, fetch_stats_concurrent, request_json
import requests
import time

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

# Base URL for Kalshi API. Defaults to the new ``api.elections.kalshi.com`` host
# but can be overridden with ``KALSHI_API_BASE``. ``FALLBACK_BASE`` preserves
# the old host for backwards compatibility if requests to the new endpoint fail.
API_BASE = os.environ.get(
    "KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2"
)
# ``KALSHI_API_BASE`` can be provided as just the host. Append the
# ``/trade-api/v2`` path if it's missing so callers don't need to include it.
if not API_BASE.rstrip('/').endswith("trade-api/v2"):
    API_BASE = API_BASE.rstrip('/') + '/trade-api/v2'
FALLBACK_BASE = "https://api.elections.kalshi.com/trade-api/v2"

MARKETS_URL = f"{API_BASE}/markets"
TRADES_ENDPOINT = f"{API_BASE}/markets/{{}}/trades"


def _request_with_fallback(url: str, *, params=None) -> dict | None:
    """Fetch *url* with fallback to the older API host if needed."""
    j = request_json(url, headers=HEADERS_KALSHI, params=params)
    if j is None and API_BASE != FALLBACK_BASE:
        alt_url = url.replace(API_BASE, FALLBACK_BASE)
        j = request_json(alt_url, headers=HEADERS_KALSHI, params=params)
    return j


def fetch_all_markets(limit: int = 1000) -> list[dict]:
    """Return a list of all Kalshi markets."""
    markets: list[dict] = []
    seen: set[str] = set()
    offset = 0
    while True:
        j = _request_with_fallback(
            MARKETS_URL, params={"limit": limit, "offset": offset}
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

def fetch_active_market_info() -> dict[str, datetime | None]:
    """Return mapping of all market ids to expiration."""
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration&source=eq.kalshi"
    rows = request_json(url, headers=SUPA_HEADERS) or []
    info: dict[str, datetime | None] = {}
    for r in rows:
        mid = r.get("market_id")
        exp_raw = r.get("expiration")
        exp_dt = parser.isoparse(exp_raw) if exp_raw else None
        if mid:
            info[mid] = exp_dt
    return info

def fetch_trade_stats(ticker: str):
    try:
        j = _request_with_fallback(TRADES_ENDPOINT.format(ticker))
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
                if price is not None and price > 1:
                    price /= 100
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
    event_prices: dict[str, dict[str, float]] = {}
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
        if exp_dt and exp_dt <= now:
            logging.info("skipping %s: expired", mid)
            skipped += 1
            continue

        last_price = m.get("last_price")
        if last_price is not None and last_price > 1:
            last_price /= 100
        yes_bid = m.get("yes_bid")
        if yes_bid is not None and yes_bid > 1:
            yes_bid /= 100
        no_bid = m.get("no_bid")
        if no_bid is not None and no_bid > 1:
            no_bid /= 100
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
            cand = mid.split("-")[-1]
            evt  = mid.rsplit("-", 1)[0]
            event_prices.setdefault(evt, {})[cand] = last_price
            outcomes.append({
                "market_id":    mid,
                "outcome_name": cand,
                "price":        last_price,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi",
            })

    # replicate full outcome set for each market
    for m in top_markets:
        mid = m.get("ticker")
        if not mid:
            continue
        evt = mid.rsplit("-", 1)[0]
        cand_self = mid.split("-")[-1]
        for cand, price in event_prices.get(evt, {}).items():
            if cand == cand_self or price is None:
                continue
            outcomes.append({
                "market_id":    mid,
                "outcome_name": cand,
                "price":        price,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi",
            })

    logging.info("writing %s snapshots and %s outcomes", len(snapshots), len(outcomes))
    # insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    # insert_to_supabase("market_outcomes", outcomes, conflict_key=None)
    if skipped:
        logging.info("skipped %s markets", skipped)
    logging.info("done")

if __name__ == "__main__":
    main()
