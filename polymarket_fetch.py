import requests

def fetch_polymarket():
    query = {
        "query": """{
            markets(first: 1000, orderBy: volume, orderDirection: desc) {
                id
                question
                volume
                outcomes { name price }
            }
        }"""
    }

    try:
        r = requests.post("https://api.thegraph.com/subgraphs/name/polymarket/polymarket", json=query)
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        print("❌ Failed to fetch or parse JSON from Polymarket:", e)
        print("🔍 Raw response text:", r.text if r else "No response object")
        return

    if "data" not in result or "markets" not in result["data"]:
        print("❌ 'data' or 'markets' key missing in response")
        print("🔍 Full response JSON:", result)
        return

    markets = result["data"]["markets"]
    cleaned = []

    for market in markets:
        if not market['outcomes']:
            continue
        prices = [o['price'] for o in market['outcomes'] if o['price'] is not None]
        if not prices:
            continue
        avg_price = sum(prices) / len(prices)
        cleaned.append({
            "market_id": market['id'],
            "price": avg_price,
            "volume": float(market.get('volume', 0)),
            "source": "polymarket"
        })

    try:
        post = requests.post("https://your-api.onrender.com/ingest", json=cleaned)
        print(f"✅ Posted {len(cleaned)} Polymarket markets: {post.status_code}")
    except Exception as e:
        print("❌ Failed to post data to your API:", e)

if __name__ == "__main__":
    fetch_polymarket()
