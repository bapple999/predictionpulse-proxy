# ✅ polymarket_fetch.py – full Polymarket market list with YES price + $-volume

import os
import time
import requests
import logging
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.parser import parse
from common import insert_to_supabase, fetch_price_24h_ago

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

GAMMA  = "https://gamma-api.polymarket.com/markets"
CLOB   = "https://clob.polymarket.com/markets/{}"
TRADES = "https://clob.polymarket.com/markets/{}/trades"

FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "100"))
MIN_DOLLAR_VOLUME = 0


def _first(obj: dict, keys: list[str]):
    """Return the first present key from *obj*"""
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None

# ───────────────── fetch helpers
def fetch_gamma(limit: int = FETCH_LIMIT, max_pages: int = 1):
    """Return full Polymarket market list via pagination."""
    out, offset = [], 0
    for _ in range(max_pages):
        r = requests.get(GAMMA, params={"limit": limit, "offset": offset}, timeout=15)
        if r.status_code == 429:
            logging.warning("Gamma 429 – sleep 10 s")
            time.sleep(10)
            continue
        r.raise_for_status()
        batch = r.json() if isinstance(r.json(), list) else r.json().get("markets", [])
        if not batch:
            break
        out.extend(batch)
        offset += limit
        logging.info("fetched %s markets", len(out))
    return out

def fetch_clob(mid: str, slug: str | None):
    for ident in (mid, slug):
        if not ident: continue
        r = requests.get(CLOB.format(ident), timeout=10)
        if r.status_code == 404: continue
        r.raise_for_status(); return r.json()
    return None

def last24h_stats(mid: str):
    try:
        r = requests.get(TRADES.format(mid), timeout=10)
        if r.status_code == 404: return 0.0, 0, None
        r.raise_for_status()
        cutoff = datetime.utcnow() - timedelta(hours=24)
        vol_ct = vol_d = 0
        for t in r.json().get("trades", []):
            if parser.parse(t["timestamp"]) >= cutoff:
                size = t["amount"]; price = t["price"] / 100
                vol_ct += size; vol_d += size * price
        vwap = round(vol_d / vol_ct, 4) if vol_ct else None
        return round(vol_d, 2), vol_ct, vwap
    except Exception as e:
        logging.warning("trade fetch failed %s: %s", mid, e)
        return 0.0, 0, None

# ───────────────────────── main
def main():
    gamma_all = fetch_gamma(limit=FETCH_LIMIT, max_pages=1)[:FETCH_LIMIT]

    now = datetime.utcnow()

    live = []
    for g in gamma_all:
        status = (g.get("status") or g.get("state") or "TRADING").upper()

        exp_raw = _first(g, ["end_date_iso", "endDate", "endTime", "end_time"])
        exp_dt = parse(exp_raw) if exp_raw else None

        price = _first(g, ["lastTradePrice", "lastPrice", "price"])
        if price is not None and price > 1:
            price = price / 100

        volume = _first(g, ["volume24Hr", "volume24hr", "volume"])
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            volume = 0.0

        dollar_volume = _first(g, ["dollarVolume24Hr", "dollar_volume_24hr"])
        if dollar_volume is None and price is not None:
            dollar_volume = round(price * volume, 2)
        else:
            try:
                dollar_volume = float(dollar_volume)
            except (TypeError, ValueError):
                dollar_volume = 0.0



        tags = []
        if g.get("category"):
            tags.append(str(g["category"]).lower())
        if g.get("categories"):
            tags.extend([str(t).lower() for t in g["categories"]])

        g.update({
            "_price": price,
            "_volume24h": volume,
            "_dollar_volume": dollar_volume,
            "_expiration": exp_dt,
            "_tags": tags or ["polymarket"],
            "_status": status,
        })
        live.append(g)

    top = sorted(live, key=lambda x: x.get("_dollar_volume", 0), reverse=True)[:FETCH_LIMIT]
    logging.info("selected %s live markets", len(top))

    ts = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for g in top:
        mid = g.get("id")
        slug = g.get("slug")
        title = g.get("title") or g.get("question") or (
            slug.replace("-", " ").title() if slug else mid
        )

        desc = g.get("description")
        event_name = g.get("category") or (g.get("categories") or [None])[0]
        exp_dt = g.get("_expiration")
        exp = exp_dt.isoformat() if exp_dt else None
        status = g.get("_status") or "TRADING"
        tags = g.get("_tags") or ["polymarket"]
        event_ticker = slug or mid

        clob = fetch_clob(mid, slug)
        tokens = (
            clob.get("outcomes") or clob.get("outcomeTokens") or []
        ) if clob else []

        yes_tok = next((t for t in tokens if t.get("name", "").lower() == "yes"), None)
        no_tok = next((t for t in tokens if t.get("name", "").lower() == "no"), None)
        price = g.get("_price")
        if yes_tok:
            alt = yes_tok.get("price") if yes_tok.get("price") is not None else yes_tok.get("probability")
            if alt is not None:
                price = alt / 100 if alt > 1 else alt

        def _best_bid(tok):
            for k in ("bestBid", "best_bid", "bid", "yesBid"):
                v = tok.get(k)
                if v is not None:
                    return v / 100 if v > 1 else v
            return None

        yes_bid = _best_bid(yes_tok) if yes_tok else None
        no_bid = _best_bid(no_tok) if no_tok else None

        vol_d, vol_ct, vwap = last24h_stats(mid)
        liquidity = None
        if clob:
            for k in ("liquidity", "totalLiquidity", "openInterest", "open_interest"):
                if k in clob and clob[k] is not None:
                    liquidity = float(clob[k])
                    break
        if liquidity is None:
            liquidity = g.get("liquidity")
            liquidity = float(liquidity) if liquidity is not None else None

        rows_m.append({
            "market_id": mid,
            "market_name": title,
            "market_description": desc,
            "event_name": event_name,
            "event_ticker": event_ticker,
            "expiration": exp,
            "tags": tags,
            "source": "polymarket",
            "status": status,
        })

        rows_s.append({
            "market_id": mid,
            "price": round(price, 4) if price is not None else None,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": vol_ct if vol_ct else None,
            "dollar_volume": vol_d if vol_d else None,
            "vwap": vwap,
            "liquidity": liquidity,
            "expiration": exp,
            "timestamp": ts,
            "source": "polymarket",
        })

        added = 0
        for t in tokens:
            p = t.get("price") if t.get("price") is not None else t.get("probability")
            if p is None:
                continue
            prob = p / 100 if p > 1 else p
            rows_o.append({
                "market_id": mid,
                "outcome_name": t.get("name"),
                "price": prob,
                "volume": t.get("volume"),
                "timestamp": ts,
                "source": "polymarket",
            })
            added += 1

        if added == 0 and price is not None:
            rows_o.append({
                "market_id": mid,
                "outcome_name": "Yes",
                "price": price,
                "volume": None,
                "timestamp": ts,
                "source": "polymarket",
            })
            rows_o.append({
                "market_id": mid,
                "outcome_name": "No",
                "price": round(1 - price, 4),
                "volume": None,
                "timestamp": ts,
                "source": "polymarket",
            })

    # ── insert in FK-safe order
    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    logging.info(
        "Inserted %s markets, %s snapshots, %s outcomes",
        len(rows_m), len(rows_s), len(rows_o),
    )
    print(
        f"Inserted {len(rows_m)} markets and {len(rows_o)} outcomes"
    )

    # diagnostics: fetch sample rows
    diag_url = f"{os.environ['SUPABASE_URL']}/rest/v1/latest_snapshots?select=market_id,source,price&order=timestamp.desc&limit=3"
    r = requests.get(diag_url, headers={
        'apikey': os.environ['SUPABASE_SERVICE_ROLE_KEY'],
        'Authorization': f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}"
    })
    if r.status_code == 200:
        logging.info("Latest snapshots sample: %s", r.json())
    else:
        logging.warning("Diagnostics fetch failed %s: %s", r.status_code, r.text[:150])

if __name__ == "__main__":
    main()
