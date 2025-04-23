import requests
import json

API_URL = "https://predictionpulse-proxy-1.onrender.com/ingest"
GAMMA_URL = "https://gamma-api.polymarket.com/markets"

def fetch_polymarket():
    try:
        response = requests.get(GAMMA_URL, params={"limit": 100})
        response.raise_for_status()
        markets = response.json()
    except Exception as e:
        print("❌ Failed to fetch from Gamma API:", e)
        return

    cleaned = []
    for market in markets:
        try:
            prices_raw = market.get("outcomePrices")
            if not prices_raw:
                continue

            # Convert stringified list to actual list of floats
            prices = json.loads(prices_raw)
            if not isinstance(prices, list) or len(prices) == 0:
                continue

            avg_price = sum(map(float, prices)) / len(prices)
            volume = float(market.get("volumeClob", 0))

            cleaned.append({
                "market_id": market.get("id"),
                "price": avg_price,
                "volume": volume,
                "source": "polymarket"
            })

        except Exception as e:
            print(f"⚠️ Skipping bad market: {e}")

    try:
        res = requests.post(API_URL, json=cleaned)
        print(f"✅ Posted {len(cleaned)} Polymarket markets: {res.status_code} | {res.text}")
    except Exception as e:
        print("❌ Failed to post to your API:", e)

if __name__ == "__main__":
    fetch_polymarket()
