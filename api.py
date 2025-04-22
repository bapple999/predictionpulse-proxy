from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from data_store import update_market, get_markets, get_top_movers

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "message": "Prediction Pulse API is live.",
        "routes": ["/markets/live", "/markets/movers", "/ingest (POST)"]
    }

@app.get("/markets/live")
def live_markets():
    return get_markets()

@app.get("/markets/movers")
def movers():
    return get_top_movers()

@app.post("/ingest")
async def ingest(request: Request):
    payload = await request.json()
    print(f"📥 Ingesting {len(payload)} markets")

    for market in payload:
        print(f"➕ Updating: {market['market_id']} | Price: {market['price']} | Volume: {market['volume']}")
        update_market(
            market_id=market["market_id"],
            price=market["price"],
            volume=market["volume"],
            source=market.get("source", "unknown")
        )

    return {"status": "success", "ingested": len(payload)}
