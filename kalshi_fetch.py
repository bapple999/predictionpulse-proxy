import os
import requests
from datetime import datetime

# Kalshi API endpoint and headers
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2/markets"
headers = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"
}

# Your backend ingest endpoint
API_URL = "https://predictionpulse-proxy-1.onrender.com/ingest"

def fetch_kalshi():
    try:
        res = requests.get(KALSHI_API, headers=headers)
        res.raise_for_status()
        data = res.json().get("markets", [])
    except Exception as e:
        print("❌ Failed to fetch Kalshi markets:", e)
        return

    cleaned = []
    for market in data:
        try:
            yes_bid = market.get("yes_bid")
            no_bid = market.get("no_bid")
            volume = market.get("volume", 0)
            market_name = market.get("title", "Unknown Market")
            ticker = market.get("ticker")

            if None in (yes_bid, no_bid) or not (0 <= yes_bid <= 1) or not (0 <= no_bid <= 1):
                continue

            prob = (yes_bid + (1 - no_bid)) / 2
            if not (0 <= prob <= 1):
                continue

            # Optional: skip markets with zero volume
            if volume == 0:
                continue

            cleaned.append({
                "market_id": ticker,
                "question": market_name,
                "price": round(prob, 3),
                "volume": volume,
                "source": "kalshi"
            })

        except Exception as e:
            print(f"⚠️ Skipping bad market: {e}")

    try:
        post = requests.post(API_URL, json=cleaned)
        print(f"✅ Posted {len(cleaned)} Kalshi markets: {post.status_code} | {post.text}")
    except Exception as e:
        print("❌ Failed to post to your API:", e)

if __name__ == "__main__":
    fetch_kalshi()
