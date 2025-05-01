import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GRAPHQL_ENDPOINT = "https://api.thegraph.com/subgraphs/name/Polymarket/polymarket"

def insert_to_supabase(payload):
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/market_snapshots",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        json=payload
    )
    print(f"✅ Supabase insert status: {res.status_code}")
    if res.status_code != 201:
        print("⚠️", res.text)

def fetch_polymarket():
    print("📡 Fetching Polymarket markets from GraphQL...")
    
    query = """
    {
      markets(first: 1000, orderBy: volume, orderDirection: desc, where: {status: "ACTIVE"}) {
        id
        question
        volume
        endTime
        outcomes {
          name
          price
        }
      }
    }
    """

    res = requests.post(GRAPHQL_ENDPOINT, json={"query": query})
    res.raise_for_status()
    data = res.json()
    markets = data.get("data", {}).get("markets", [])
    print(f"🔍 Retrieved {len(markets)} markets")

    payload = []

    for market in markets:
        outcomes = market.get("outcomes", [])
        try:
            prices = [float(o["price"]) for o in outcomes if o.get("price") is not None]
            if not prices:
                continue
            avg_price = sum(prices) / len(prices)
        except Exception as e:
            print(f"⚠️ Skipping market {market['id']} due to price error: {e}")
            continue

        payload.append({
            "market_id": market.get("id", ""),
            "market_name": market.get("question", ""),
            "market_description": None,
            "event_name": "Polymarket",
            "event_ticker": None,
            "price": round(avg_price, 4),
            "yes_bid": None,
            "no_bid": None,
            "volume": float(market.get("volume", 0)),
            "liquidity": None,
            "status": "active",
            "expiration": market.get("endTime"),
            "tags": ["polymarket"],
            "source": "polymarket_graphql",
            "timestamp": datetime.utcnow().isoformat()
        })

    print(f"📦 Prepared {len(payload)} market entries for Supabase")
    insert_to_supabase(payload)

if __name__ == "__main__":
    fetch_polymarket()
