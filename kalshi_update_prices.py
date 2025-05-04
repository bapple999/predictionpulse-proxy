# kalshi_update_prices.py  – runs every 5 minutes
import requests
from datetime import datetime
from common import insert_to_supabase   # helper in the same folder

# Public endpoint (no auth needed for market list & bids)
MARKETS_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets"

def main() -> None:
    # No headers → treated as a public read‑only request
    resp = requests.get(MARKETS_ENDPOINT, timeout=20)
    resp.raise_for_status()

    ts = datetime.utcnow().isoformat() + "Z"
    snaps, outs = [], []

    for m in resp.json().get("markets", []):
        mid     = m["ticker"]
        yes_bid = m.get("yes_bid")
        no_bid  = m.get("no_bid")
        prob    = (
            (yes_bid + (1 - no_bid)) / 2
            if yes_bid is not None and no_bid is not None
            else None
        )

        snaps.append(
            {
                "market_id": mid,
                "price":      round(prob, 4) if prob is not None else None,
                "yes_bid":    yes_bid,
                "no_bid":     no_bid,
                "volume":     m.get("volume"),
                "liquidity":  m.get("open_interest"),
                "timestamp":  ts,
                "source":     "kalshi",
            }
        )

        if yes_bid is not None:
            outs.append(
                {
                    "market_id":   mid,
                    "outcome_name":"Yes",
                    "price":        yes_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                }
            )
        if no_bid is not None:
            outs.append(
                {
                    "market_id":   mid,
                    "outcome_name":"No",
                    "price":        1 - no_bid,
                    "volume":       None,
                    "timestamp":    ts,
                    "source":       "kalshi",
                }
            )

    # plain INSERTs (no unique constraint on these history tables)
    insert_to_supabase("market_snapshots", snaps, conflict_key=None)
    insert_to_supabase("market_outcomes",  outs,  conflict_key=None)

    print(f"✅ Snapshots {len(snaps)} | Outcomes {len(outs)}")

if __name__ == "__main__":
    main()
