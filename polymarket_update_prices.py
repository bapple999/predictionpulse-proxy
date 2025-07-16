import os
import time
import logging
import requests
from datetime import datetime, timedelta
from dateutil import parser
from common import (
    insert_to_supabase,
    fetch_clob,
    last24h_stats,
    CLOB_URL,
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "100"))
SUPA_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# only refresh markets expiring within this window
UPDATE_WINDOW_DAYS = 7

TRADES = os.environ.get(
    "POLYMARKET_TRADES_URL", "https://clob.polymarket.com/markets/{}/trades"
)


def request_json(url: str, headers=None, params=None, tries: int = 3, backoff: float = 1.5):
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

# ───────────────── helpers
# `fetch_clob` and `last24h_stats` are imported from ``common`` so that they
# respect any environment-based overrides for Polymarket endpoints.

def load_active_market_info(days: int = UPDATE_WINDOW_DAYS) -> dict[str, datetime | None]:
    url = f"{SUPABASE_URL}/rest/v1/markets?select=market_id,expiration&source=eq.polymarket"
    rows = request_json(url, headers=SUPA_HEADERS) or []
    now = datetime.utcnow()
    future = now + timedelta(days=days)
    info: dict[str, datetime | None] = {}
    for r in rows:
        mid = r.get("market_id")
        exp_raw = r.get("expiration")
        exp_dt = parser.isoparse(exp_raw) if exp_raw else None
        if exp_dt is None or (now <= exp_dt <= future):
            info[mid] = exp_dt
    return info

# ───────────────── main
def main():
    now = datetime.utcnow()
    ts = now.isoformat() + "Z"
    active = load_active_market_info()
    logging.info("refreshing %s polymarket prices", len(active))

    snapshots, outcomes = [], []

    for mid, exp_dt in list(active.items())[:FETCH_LIMIT]:
        if exp_dt and exp_dt <= now:
            logging.info("skipping %s: expired", mid)
            continue
        if exp_dt and exp_dt - now > timedelta(days=UPDATE_WINDOW_DAYS):
            logging.info("skipping %s: expires beyond window", mid)
            continue

        clob = fetch_clob(mid)
        if not clob:
            logging.info("clob fetch failed for %s", mid)
            continue

        toks = (clob.get("outcomes") or clob.get("outcomeTokens") or [])
        if not toks:
            logging.info("no outcome data for %s", mid)
            continue

        yes_tok = next((t for t in toks if t.get("name", "").lower() == "yes"), None)
        price = None
        if yes_tok:
            price = yes_tok.get("price")
            if price is None:
                price = yes_tok.get("probability")
            if price is not None:
                price = price / 100
        else:
            logging.info("missing YES token for %s", mid)
        if price is None:
            logging.info("no price for %s", mid)

        vol_d, vol_ct, vwap = last24h_stats(mid)
        if vol_ct == 0:
            logging.info("no recent trades for %s", mid)

        snapshots.append({
            "market_id":mid,
            "price":round(price,4) if price is not None else None,
            "yes_bid":None,"no_bid":None,
            "volume":vol_ct,"dollar_volume":vol_d,"vwap":vwap,
            "liquidity":None,"timestamp":ts,"source":"polymarket_clob"
        })

        for t in toks:
            p = t.get("price") if t.get("price") is not None else t.get("probability")
            if p is None: continue
            outcomes.append({
                "market_id":mid,"outcome_name":t["name"],
                "price":p/100,"volume":None,
                "timestamp":ts,"source":"polymarket_clob"
            })

    logging.info("writing %s snapshots • %s outcomes", len(snapshots), len(outcomes))
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    insert_to_supabase("market_outcomes",  outcomes,  conflict_key=None)
    logging.info("done")

if __name__ == "__main__":
    from datetime import datetime
    main()
