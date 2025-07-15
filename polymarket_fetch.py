# ✅ polymarket_fetch.py – fetch Polymarket markets with price + dollar volume

import logging
from datetime import datetime, timezone
from dateutil.parser import parse
from common import insert_to_supabase, fetch_gamma, fetch_clob, last24h_stats

MIN_DOLLAR_VOLUME = 100


def _first(obj: dict, keys: list[str]):
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def main():
    gamma_all = fetch_gamma()
    now = datetime.now(timezone.utc)
    closed = {"RESOLVED", "FINALIZED", "SETTLED", "CANCELLED"}
    live = []

    for g in gamma_all:
        status = (g.get("status") or g.get("state") or "TRADING").upper()
        if status in closed:
            continue

        exp_raw = _first(g, ["end_date_iso", "endDate", "endTime", "end_time"])
        exp_dt = parse(exp_raw) if exp_raw else None
        if exp_dt:
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            else:
                exp_dt = exp_dt.astimezone(timezone.utc)
        if exp_dt and exp_dt <= now:
            continue

        price = _first(g, ["lastTradePrice", "lastPrice", "price"])
        if price and price > 1:
            price /= 100

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

        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue

        tags = []
        if g.get("category"):
            tags.append(str(g["category"]).lower())
        if g.get("categories"):
            tags.extend([str(t).lower() for t in g["categories"]])

        g.update(
            {
                "_price": price,
                "_volume24h": volume,
                "_dollar_volume": dollar_volume,
                "_expiration": exp_dt,
                "_tags": tags or ["polymarket"],
                "_status": status,
            }
        )
        live.append(g)

    top = sorted(live, key=lambda x: x.get("_dollar_volume", 0), reverse=True)
    logging.info("selected %s live markets", len(top))

    rows_m, rows_s, rows_o = [], [], []
    ts = now.isoformat().replace("+00:00", "Z")

    for g in top:
        mid = g.get("id")
        slug = g.get("slug")
        title = (
            g.get("title")
            or g.get("question")
            or (slug or mid).replace("-", " ").title()
        )
        exp_dt = g.get("_expiration")
        exp = exp_dt.isoformat().replace("+00:00", "Z") if exp_dt else None
        status = g.get("_status") or "TRADING"
        tags = g.get("_tags") or ["polymarket"]

        price = g.get("_price")
        clob = fetch_clob(mid, slug)
        tokens = (
            (clob.get("outcomes") or clob.get("outcomeTokens") or []) if clob else []
        )
        yes_tok = next((t for t in tokens if t.get("name", "").lower() == "yes"), None)
        if yes_tok:
            alt = yes_tok.get("price", yes_tok.get("probability"))
            if alt is not None:
                price = alt / 100

        vol_d, vol_ct, vwap = last24h_stats(mid)
        if vol_d == 0.0:
            vol_d = g.get("_dollar_volume", 0.0)
            vol_ct = g.get("_volume24h", 0)
            if vwap is None:
                vwap = price if price is not None else None
        if vol_d < MIN_DOLLAR_VOLUME:
            continue

        logging.info(
            "Inserting market %s — price: %s, $vol: %s, exp: %s",
            mid,
            price,
            vol_d,
            exp,
        )

        rows_m.append(
            {
                "market_id": mid,
                "market_name": title,
                "market_description": g.get("description") or "",
                "event_name": title,
                "event_ticker": mid,
                "expiration": exp,
                "tags": tags,
                "source": "polymarket",
                "status": status,
            }
        )

        rows_s.append(
            {
                "market_id": mid,
                "price": round(price, 4) if price is not None else None,
                "yes_bid": None,
                "no_bid": None,
                "volume": vol_ct,
                "dollar_volume": vol_d,
                "vwap": vwap,
                "liquidity": None,
                "expiration": exp,
                "timestamp": ts,
                "source": "polymarket",
            }
        )

        for t in tokens:
            p = t.get("price", t.get("probability"))
            if p is None:
                continue
            rows_o.append(
                {
                    "market_id": mid,
                    "outcome_name": t.get("name"),
                    "price": p / 100,
                    "volume": t.get("volume"),
                    "timestamp": ts,
                    "source": "polymarket",
                }
            )

    insert_to_supabase("markets", rows_m)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)

    logging.info(
        "Inserted %s markets, %s snapshots, %s outcomes",
        len(rows_m),
        len(rows_s),
        len(rows_o),
    )


if __name__ == "__main__":
    main()
