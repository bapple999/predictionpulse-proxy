from fastapi import FastAPI
from data_store import get_top_movers, get_all_markets
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/markets/movers")
def movers():
    return get_top_movers()

@app.get("/markets/live")
def live():
    return get_all_markets()
