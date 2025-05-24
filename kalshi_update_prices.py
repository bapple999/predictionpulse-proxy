def main():
    ts = datetime.utcnow().isoformat() + "Z"
    markets = fetch_all_markets()

    # ✅ Filter to top 200 markets by volume
    top_markets = sorted(
        [m for m in markets if isinstance(m.get("volume"), (int, float))],
        key=lambda m: m["volume"],
        reverse=True
    )[:200]

    print(f"🏆 Processing top {len(top_markets)} markets by volume", flush=True)

    snapshots, outcomes = [], []

    for m in top_markets:
        mid     = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid  = m.get("no_bid")
        prob    = (
            (yes_bid + (1 - no_bid)) / 2
            if yes_bid is not None and no_bid is not None
            else None
        )

        snapshots.append({
            "market_id":  mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi",
        })

        title = m.get("title") or m.get("description") or mid

        if yes_bid is not None:
            outcomes.append({
                "market_id":    mid,
                "outcome_name": title,
                "price":        yes_bid,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi",
            })

    print("📏 Writing snapshots to Supabase…", flush=True)
    insert_to_supabase("market_snapshots", snapshots, conflict_key=None)
    print("📏 Writing outcomes to Supabase…", flush=True)
    insert_to_supabase("market_outcomes",  outcomes, conflict_key=None)
    print(f"✅ Snapshots {len(snapshots)} | Outcomes {len(outcomes)}", flush=True)
