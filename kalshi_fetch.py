"""Load events and candidate markets from Kalshi and store them."""

import os
import requests
from datetime import datetime
from dateutil.parser import parse
from common import insert_to_supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS_KALSHI = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}",
    "Content-Type": "application/json",
}

EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"
MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"


def fetch_events() -> list[dict]:
    """Return a list of election events."""
    r = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15)
    r.raise_for_status()
    return r.json().get("events", [])


def fetch_markets(event_ticker: str) -> list[dict]:
    """Return markets associated with *event_ticker*."""
    r = requests.get(
        MARKETS_URL,
        headers=HEADERS_KALSHI,
        params={"event_ticker": event_ticker},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("markets", [])


def main() -> None:
    events = fetch_events()
    ts = datetime.utcnow().isoformat() + "Z"

    rows_m: list[dict] = []
    rows_s: list[dict] = []
    rows_o: list[dict] = []

    for event in events:
        event_ticker = event.get("ticker")
        title = event.get("title") or event_ticker
        if not event_ticker:
            continue
        markets = fetch_markets(event_ticker)

        for m in markets:
            ticker = m.get("ticker")
            if not ticker:
                continue

            candidate = ticker.split("-")[-1]
            price = m.get("last_price")
            expiration_raw = m.get("close_time") or m.get("closeTime")
            expiration = parse(expiration_raw).isoformat() if expiration_raw else None

            rows_m.append(
                {
                    "market_id": ticker,
                    "market_name": candidate,
                    "market_description": title,
                    "event_name": title,
                    "event_ticker": event_ticker,
                    "expiration": expiration,
                    "tags": ["kalshi"],
                    "source": "kalshi",
                    "status": m.get("status") or "TRADING",
                }
            )

            rows_s.append(
                {
                    "market_id": ticker,
                    "price": round(price, 4) if price is not None else None,
                    "yes_bid": m.get("yes_bid"),
                    "no_bid": m.get("no_bid"),
                    "volume": m.get("volume"),
                    "dollar_volume": None,
                    "vwap": None,
                    "liquidity": m.get("open_interest"),
                    "expiration": expiration,
                    "timestamp": ts,
                    "source": "kalshi",
                }
            )

            rows_o.append(
                {
                    "market_id": ticker,
                    "outcome_name": candidate,
                    "price": price,
                    "volume": None,
                    "timestamp": ts,
                    "source": "kalshi",
                }
            )

    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    diag_url = (
        f"{SUPABASE_URL}/rest/v1/latest_snapshots?select=market_id,source,price&order=timestamp.desc&limit=3"
    )
    r = requests.get(
        diag_url,
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
    )
    if r.status_code == 200:
        print("Latest snapshots sample:", r.json())
    else:
        print("⚠️ Diagnostics fetch failed", r.status_code, r.text[:150])


if __name__ == "__main__":
    main()
