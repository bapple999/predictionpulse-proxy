import asyncio
import websockets
import json
import os
from datetime import datetime, timedelta
from data_store import update_market

KALSHI_KEY = os.environ['KALSHI_API_KEY']
KALSHI_SECRET = os.environ['KALSHI_API_SECRET']

async def run_kalshi_ws():
    uri = "wss://api.elections.kalshi.com/trade-api/ws"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "auth",
            "api_key": KALSHI_KEY,
            "api_secret": KALSHI_SECRET
        }))

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "market_updates"
        }))

        print("✅ Subscribed to Kalshi market_updates")
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "market_updates":
                update_market(
                    market_id=data['market_ticker'],
                    price=data['yes_price'],
                    volume=data.get('volume', 0),
                    source='kalshi'
                )

if __name__ == "__main__":
    asyncio.run(run_kalshi_ws())
