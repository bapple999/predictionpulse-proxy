import os
import logging
from datetime import datetime, timezone
from dateutil import parser
from common import (
    insert_to_supabase,
    last24h_stats,
    CLOB_URL,
    request_json,
)
import requests
import time

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "100"))
SUPA_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")



# `last24h_stats` is imported from ``common`` so that it respects any
# environment-based overrides for Polymarket endpoints. CLOB fetching with
# retries is implemented locally in this module.

def load_active_market_info() -> dict[str, dict]:
    """Return mapping of active Polymarket ids to info dicts."""
    url = (
        f"{SUPABASE_URL}/rest/v1/markets"
        f"?select=market_id,slug,event_ticker,expiration,status,liquidity_type"
        f"&source=eq.polymarket"
    )
    rows = request_json(url, headers=SUPA_HEADERS) or []
    now = datetime.now(timezone.utc)
    info: dict[str, dict] = {}
    for r in rows:
        mid = r.get("market_id")
        slug = r.get("slug") or r.get("event_ticker")
        exp_raw = r.get("expiration")
        exp_dt = parser.isoparse(exp_raw) if exp_raw else None
        status = (r.get("status") or "").upper()
        if (
            mid
            and status not in {"RESOLVED", "CANCELLED"}
            and (exp_dt is None or exp_dt > now)
        ):
            info[mid] = {
                "slug": slug,
                "expiration": exp_dt,
                "status": status,
                "liquidity_type": (r.get("liquidity_type") or "").lower(),
            }
    return info


def fetch_clob_retry(mid: str, slug: str | None = None, *, tries: int = 3,
                     backoff: float = 1.5):
    """Fetch CLOB data with retries and logging."""
    for ident in filter(None, [mid, slug]):
        delay = backoff
        for attempt in range(tries):
            try:
                r = requests.get(CLOB_URL.format(ident), timeout=8)
                if r.status_code == 404:
                    logging.info("clob 404 for %s", ident)
                    break
                if 500 <= r.status_code < 600:
                    logging.warning(
                        "server error %s for %s: %s",
                        r.status_code,
                        ident,
                        r.text[:150],
                    )
                    if attempt < tries - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                if r.status_code != 200:
                    logging.warning(
                        "clob fetch failed for %s: %s %s",
                        ident,
                        r.status_code,
                        r.text[:150],
                    )
                    break
                return r.json()
            except requests.RequestException as e:
                logging.warning("clob request exception for %s: %s", ident, e)
                if attempt < tries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
        # try next identifier (slug or id)
    return None

# ───────────────── main
def main():
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    active = load_active_market_info()
    logging.info("refreshing %s polymarket prices", len(active))

    snapshots, outcomes = [], []

    for mid, info in list(active.items())[:FETCH_LIMIT]:
        slug = info.get("slug")
        exp = info.get("expiration")
        status = info.get("status", "").upper()
        liquidity_type = info.get("liquidity_type")

        if exp and exp <= now:
            logging.info("skip expired market %s", mid)
            continue

        if liquidity_type != "clob" or status != "TRADING" or not (slug or mid):
            logging.warning("skip non-clob or non-trading market %s", mid)
            continue

        clob = fetch_clob_retry(mid, slug)
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
