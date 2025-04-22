import os
import requests

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2/markets"
headers = {
    "Authorization": f"Bearer {os.environ['KALSHI_API_KEY']}"
}

def fetch_kalshi():
    res = requests.get(KALSHI_API, headers=headers)
    res.raise_for_status()
    data = res.json().get("markets", [])

    cleaned = []

    for market in data:
        yes_bid = market.get("yes_bid")
        no_bid = market.get("no_bid")

        if yes_bid is None or no_bid is None:
            continue

        prob = (yes_bid + (1 - no_bid)) / 2
        cleaned.append({
            "market_id": market.get("ticker"),
            "price": prob,
            "volume": market.get("volume", 0),
            "source": "kalshi"
        })

    post = requests.post("https://your-api.onrender.com/ingest", json=cleaned)
    print(f"✅ Posted {len(cleaned)} Kalshi markets: {post.status_code}")

if __name__ == "__main__":
    fetch_kalshi()
