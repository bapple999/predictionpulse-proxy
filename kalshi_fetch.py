def main():
    events = fetch_events()
    raw_markets = fetch_all_markets()

    # ✅ Sort markets by volume and keep only top 200
    sorted_markets = sorted(
        [m for m in raw_markets if isinstance(m.get("volume"), (int, float))],
        key=lambda x: x.get("volume", 0),
        reverse=True
    )[:200]

    print(f"🏆 Markets to ingest: {len(sorted_markets)} (top 200 by volume)", flush=True)

    now_ts = datetime.utcnow().isoformat() + "Z"
    rows_m, rows_s, rows_o = [], [], []

    for m in sorted_markets:
        ticker = m.get("ticker")
        if not ticker:
            continue

        ev = events.get(m.get("event_ticker")) or {}

        last_price = m.get("last_price")
        yes_bid = m.get("yes_bid")
        no_bid = m.get("no_bid")
        volume = m.get("volume")
        liquidity = m.get("open_interest")
        expiration = safe_ts(m.get("expiration"))

        # --- markets table ----------------------------------------------------
        rows_m.append({
            "market_id": ticker,
            "market_name": m.get("title") or m.get("description") or "",
            "market_description": m.get("description") or "",
            "event_name": ev.get("title") or ev.get("name") or "",
            "event_ticker": m.get("event_ticker") or "",
            "expiration": expiration,
            "tags": m.get("tags") or [],
            "source": "kalshi",
            "status": m.get("status") or "",
        })

        # --- snapshots table --------------------------------------------------
        rows_s.append({
            "market_id": ticker,
            "price": last_price,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "volume": volume,
            "liquidity": liquidity,
            "expiration": expiration,
            "timestamp": now_ts,
            "source": "kalshi",
        })

        # --- outcomes table ---------------------------------------------------
        rows_o.append({
            "market_id": ticker,
            "outcome_name": "Yes",
            "price": last_price,
            "volume": volume,
            "timestamp": now_ts,
            "source": "kalshi",
        })

    print("💾 Upserting markets…", flush=True)
    insert_to_supabase("markets", rows_m)
    print("💾 Writing snapshots…", flush=True)
    insert_to_supabase("market_snapshots", rows_s, conflict_key=None)
    print("💾 Writing outcomes…", flush=True)
    insert_to_supabase("market_outcomes", rows_o, conflict_key=None)
    print(f"✅ Markets {len(rows_m)} | Snapshots {len(rows_s)} | Outcomes {len(rows_o)}", flush=True)
