"""Load events and candidate markets from Kalshi and store them."""

import os
import json
from datetime import datetime
from dateutil.parser import parse


from common import insert_to_supabase, fetch_price_24h_ago, request_json

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ.get('KALSHI_API_KEY', 'test-key')}",
    "Content-Type": "application/json",
}

# Base URL for Kalshi API. The default now points to the new
# ``api.elections.kalshi.com`` host. ``KALSHI_API_BASE`` can override this
# value. ``FALLBACK_BASE`` retains the old host for backwards compatibility
# if the newer host fails.
API_BASE = os.environ.get(
    "KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2"
)
FALLBACK_BASE = "https://trading-api.kalshi.com/trade-api/v2"

EVENTS_URL = f"{API_BASE}/events"
MARKETS_URL = f"{API_BASE}/markets"


def _request_with_fallback(url: str, *, params=None) -> dict | None:
    """Return JSON from *url* with fallback to the older API host."""
    j = request_json(url, headers=HEADERS_KALSHI, params=params)
    if j is None and API_BASE != FALLBACK_BASE:
        alt_url = url.replace(API_BASE, FALLBACK_BASE)
        j = request_json(alt_url, headers=HEADERS_KALSHI, params=params)
    return j


def fetch_events() -> list[dict]:
    """Return a list of election events."""
    j = _request_with_fallback(EVENTS_URL)
    print("\N{POLICE CARS REVOLVING LIGHT} Kalshi response:")
    print(json.dumps(j, indent=2) if j is not None else "None")
    return j.get("events", []) if isinstance(j, dict) else []


def fetch_markets(event_ticker: str) -> list[dict]:
    """Return markets associated with *event_ticker*."""
    j = _request_with_fallback(
        MARKETS_URL, params={"event_ticker": event_ticker}
    )
    return j.get("markets", []) if isinstance(j, dict) else []


def format_market_row(event: dict, market: dict) -> dict:
    """Return a dict for the markets table using *event* and *market* data."""
    ticker = market.get("ticker")
    candidate = ticker.split("-")[-1] if ticker else None
    expiration_raw = market.get("close_time") or market.get("closeTime")
    expiration = parse(expiration_raw).isoformat() if expiration_raw else None
    event_ticker = event.get("ticker") or event.get("event_ticker")
    title = event.get("title") or event_ticker
    return {
        "market_id": ticker,
        "market_name": candidate,
        "market_description": title,
        "event_name": title,
        "event_ticker": event_ticker,
        "expiration": expiration,
        "tags": ["kalshi"],
        "source": "kalshi",
        "status": market.get("status") or "TRADING",
    }


def main() -> None:
    events = fetch_events()
    ts = datetime.utcnow().isoformat() + "Z"

    rows_e: list[dict] = []
    rows_m: list[dict] = []
    rows_p: list[dict] = []
    rows_s: list[dict] = []
    rows_o: list[dict] = []

    for event in events:
        event_ticker = event.get("ticker") or event.get("event_ticker")
        title = event.get("title") or event_ticker
        if not event_ticker:
            continue
        rows_e.append({
            "event_id": event_ticker,
            "title": title,
            "source": "kalshi",
        })

        markets = fetch_markets(event_ticker)

        for m in markets:
            ticker = m.get("ticker")
            if not ticker:
                continue
            row_m = format_market_row(event, m)

            candidate = row_m["market_name"]
            expiration = row_m["expiration"]
            price = m.get("last_price")

            yes_bid = m.get("yes_bid")
            yes_ask = m.get("yes_ask")
            avg_price = None
            if yes_bid is not None and yes_ask is not None:
                avg_price = round((yes_bid + yes_ask) / 2, 4)
            elif price is not None:
                avg_price = round(price, 4)

            volume = m.get("volume")
            dollar_volume = None
            if volume is not None and avg_price is not None:
                dollar_volume = round(volume * avg_price, 2)

            past = fetch_price_24h_ago(ticker)
            change_24h = None
            pct_change = None
            if past is not None and avg_price is not None:
                change_24h = round(avg_price - past, 4)
                pct_change = round(change_24h / past * 100, 2) if past else None

            rows_m.append(row_m)

            rows_s.append(
                {
                    "market_id": ticker,
                    "price": avg_price,
                    "yes_bid": yes_bid,
                    "no_bid": yes_ask,
                    "volume": volume,
                    "dollar_volume": dollar_volume,
                    "vwap": None,
                    "liquidity": m.get("open_interest"),
                    "expiration": expiration,
                    "timestamp": ts,
                    "source": "kalshi",
                }
            )

            rows_p.append(
                {
                    "market_id": ticker,
                    "price": avg_price,
                    "change_24h": change_24h,
                    "percent_change_24h": pct_change,
                    "timestamp": ts,
                    "source": "kalshi",
                }
            )

            rows_o.append(
                {
                    "market_id": ticker,
                    "outcome_name": candidate,
                    "price": avg_price,
                    "volume": None,
                    "timestamp": ts,
                    "source": "kalshi",
                }
            )

    insert_to_supabase("events", rows_e)
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_prices", rows_p, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    diag_url = (
        f"{SUPABASE_URL}/rest/v1/latest_snapshots?select=market_id,source,price&order=timestamp.desc&limit=3"
    )
    j = request_json(
        diag_url,
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
    )
    if isinstance(j, list):
        print("Latest snapshots sample:", j)
    else:
        print("⚠️ Diagnostics fetch failed")


if __name__ == "__main__":
    main()
