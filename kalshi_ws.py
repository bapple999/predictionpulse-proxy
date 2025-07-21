import os
import asyncio
import json
import websockets

WS_URL = os.environ.get("KALSHI_WS_URL", "wss://api.elections.kalshi.com/ws/v2")
API_KEY = os.environ.get("KALSHI_API_KEY")
if not API_KEY:
    raise RuntimeError("KALSHI_API_KEY must be set")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

async def listen_ticker():
    async with websockets.connect(WS_URL, extra_headers=HEADERS, ping_interval=10, ping_timeout=10) as ws:
        cmd = {"id": 1, "cmd": "subscribe", "params": {"channels": ["ticker_v2"]}}
        await ws.send(json.dumps(cmd))
        async for message in ws:
            data = json.loads(message)
            if data.get("type") == "ticker_v2":
                print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(listen_ticker())
