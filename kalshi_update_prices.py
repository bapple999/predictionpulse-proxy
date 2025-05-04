import os
import requests
from datetime import datetime
from common import insert_to_supabase        # ← flat‑folder import

MARKETS_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets"
HEADERS_KALSHI   = {"Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"}

def main() -> None:
    resp = requests.get(MARKETS_ENDPOINT, headers=HEADERS_KALSHI, timeout=20)
    resp.raise_for_status()

    ts    = datetime.utcnow().isoformat() + "Z"
    snaps, outs = [], []

    for m in resp.json().get("markets", []):
        mid      = m["ticker"]
        yes_bid  = m.get("yes_bid")
        no_bid   = m.get("no_bid")
        prob     = ((yes_bid + (1 - no_bid)) / 2
                     if yes_bid is not None and no_bid is not None else None)

        snaps.append({
            "market_id": mid,
            "price":      round(prob, 4) if prob is not None else None,
            "yes_bid":    yes_bid,
            "no_bid":     no_bid,
            "volume":     m.get("volume"),
            "liquidity":  m.get("open_interest"),
            "timestamp":  ts,
            "source":     "kalshi"
        })

        if yes_bid is not None:
            outs.append({
                "market_id":   mid,
                "outcome_name":"Yes",
                "price":        yes_bid,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })
        if no_bid is not None:
            outs.append({
                "market_id":   mid,
                "outcome_name":"No",
                "price":        1 - no_bid,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })

    insert_to_supabase("market_snapshots", snaps)
    insert_to_supabase("market_outcomes",  outs)
    print(f"✅ Snapshots {len(snaps)} | Outcomes {len(outs)}")

if __name__ == "__main__":
    main()
