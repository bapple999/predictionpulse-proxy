import os, requests
from datetime import datetime
from scripts.common import insert_to_supabase

MARKETS_ENDPOINT = "https://api.elections.kalshi.com/trade-api/v2/markets"
HEADERS_KALSHI   = {"Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"}

def main():
    r = requests.get(MARKETS_ENDPOINT, headers=HEADERS_KALSHI", timeout=20)
    r.raise_for_status()
    ts        = datetime.utcnow().isoformat() + "Z"
    snaps, outs = [], []

    for m in r.json().get("markets", []):
        mid, yes, no = m["ticker"], m.get("yes_bid"), m.get("no_bid")
        prob         = ((yes + (1 - no)) / 2) if yes is not None and no is not None else None

        snaps.append({
            "market_id": mid,
            "price":     round(prob, 4) if prob is not None else None,
            "yes_bid":   yes,
            "no_bid":    no,
            "volume":    m.get("volume"),
            "liquidity": m.get("open_interest"),
            "timestamp": ts,
            "source":    "kalshi"
        })

        if yes is not None:
            outs.append({
                "market_id":   mid,
                "outcome_name":"Yes",
                "price":        yes,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })
        if no is not None:
            outs.append({
                "market_id":   mid,
                "outcome_name":"No",
                "price":        1 - no,
                "volume":       None,
                "timestamp":    ts,
                "source":       "kalshi"
            })

    insert_to_supabase("market_snapshots", snaps)
    insert_to_supabase("market_outcomes",  outs)

if __name__ == "__main__":
    main()
