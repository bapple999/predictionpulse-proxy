from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from data_store import update_market, get_markets, get_top_movers

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/markets/live")
def live_markets():
    return get_markets()

@app.get("/markets/movers")
def movers():
    return get_top_movers()

@app.post("/ingest")
async def ingest(request: Request):
    payload = await request.json()
    for market in payload:
        update_market(
            market_id=market["market_id"],
            price=market["price"],
            volume=market["volume"],
            source=market.get("source", "unknown")
        )
    return {"status": "ok"}
