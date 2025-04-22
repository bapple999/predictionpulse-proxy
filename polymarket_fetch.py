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

    r = requests.post("https://api.thegraph.com/subgraphs/name/polymarket/polymarket", json=query)
    try:
        result = r.json()
    except Exception as e:
        print("❌ Failed to parse JSON:", e)
        print("🔍 Raw response:", r.text)
        return

    if "data" not in result:
        print("❌ No 'data' in response. Full response:", result)
        return

    data = result["data"]["markets"]


    cleaned = []

    for market in data:
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

    post = requests.post("https://your-api.onrender.com/ingest", json=cleaned)
    print(f"✅ Posted {len(cleaned)} Polymarket markets: {post.status_code}")

if __name__ == "__main__":
    fetch_polymarket()
