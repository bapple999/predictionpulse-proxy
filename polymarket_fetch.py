import requests
from datetime import datetime
import pytz
import os

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://oedvfgnnheevwhpubvzf.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your_supabase_key_here")  # Replace with your actual key

# GraphQL endpoint for Polymarket
GRAPHQL_ENDPOINT = "https://api.thegraph.com/subgraphs/name/Polymarket/polymarket"

# GraphQL query to fetch markets
query = """
{
  markets(first: 1000, orderBy: volume, orderDirection: desc) {
    id
    question
    outcomes {
      id
      name
      price
      yesBid
      noBid
    }
    volume
    liquidity
    endTime
    tags
  }
}
"""

def fetch_polymarket_data():
    print("📡 Fetching Polymarket markets from GraphQL...")
    response = requests.post(GRAPHQL_ENDPOINT, json={'query': query})
    if response.status_code != 200:
        print(f"❌ Failed to fetch data: {response.status_code}")
        return []

    data = response.json()
    markets = data.get("data", {}).get("markets", [])
    print(f"🔍 Retrieved {len(markets)} markets")
    return markets

def transform_market_data(markets):
    transformed = []
    for market in markets:
        for outcome in market.get("outcomes", []):
            transformed.append({
                "market_id": market["id"],
                "market_name": market["question"],
                "price": float(outcome.get("price", 0)),
                "volume": float(market.get("volume", 0)),
                "liquidity": float(market.get("liquidity", 0)),
                "source": "polymarket",
                "timestamp": datetime.now(pytz.utc).isoformat(),
                "yes_bid": float(outcome.get("yesBid", 0)),
                "no_bid": float(outcome.get("noBid", 0)),
                "market_description": None,
                "event_name": None,
                "event_ticker": None,
                "status": None,
                "expiration": datetime.fromtimestamp(int(market.get("endTime", 0)), pytz.utc).isoformat() if market.get("endTime") else None,
                "tags": market.get("tags", [])
            })
    print(f"📦 Prepared {len(transformed)} market entries for Supabase")
    return transformed

def insert_into_supabase(data):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/market_snapshots", headers=headers, json=data)
    if response.status_code in [200, 201]:
        print(f"✅ Supabase insert status: {response.status_code}")
    else:
        print(f"❌ Supabase insert failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    markets = fetch_polymarket_data()
    if markets:
        transformed_data = transform_market_data(markets)
        insert_into_supabase(transformed_data)
