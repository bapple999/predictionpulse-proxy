# 🧠 Prediction Pulse

A real-time prediction market dashboard powered by Kalshi + Polymarket. Built to monitor top markets, volume, and 24h price changes — just like a CoinMarketCap for prediction markets.

---

## 🚀 Live Features
- 🔁 Real-time Kalshi market updates via WebSocket
- 🔄 5-minute polling for Polymarket via The Graph
- 📊 In-memory tracking of all markets and 24h % changes
- 🔌 FastAPI backend serving `/markets/live` and `/markets/movers`

---

## 📁 Project Structure

```
predictionpulse/
├── api.py                 # FastAPI server
├── kalshi_ws_live.py      # Kalshi WebSocket listener
├── polymarket_fetch.py    # Polymarket GraphQL polling script
├── data_store.py          # In-memory store for live and 24h data
├── requirements.txt       # Python dependencies
└── render.yaml            # Render deployment blueprint
```

---

## ✅ Requirements
- Python 3.8+
- Environment variables:
  - `KALSHI_API_KEY`
  - `KALSHI_API_SECRET`

---

## 🔧 Local Development
```bash
pip install -r requirements.txt

# Run FastAPI server
uvicorn api:app --reload

# Run Kalshi listener (in another terminal)
python kalshi_ws_live.py

# Poll Polymarket manually
python polymarket_fetch.py
```

---

## 🛰 Deployment (Render)
This project uses **Render Blueprint (render.yaml)** to deploy:
- 🌐 FastAPI Web API (`/markets/live`, `/markets/movers`)
- 🔁 Background worker (Kalshi WebSocket)
- ⏱ 5-minute cron (Polymarket polling)

1. Push this repo to GitHub
2. Go to [Render > New Blueprint](https://dashboard.render.com/blueprint)
3. Paste the repo link
4. Add your Kalshi API key + secret as environment variables
5. Deploy 🚀

---

## 📬 API Endpoints
```http
GET /markets/live       # All current tracked markets
GET /markets/movers     # Top 10 markets by 24h % change
```

---

## 🧱 Next Ideas
- Add Supabase for historical charts
- Add frontend with Framer or React
- Add alerts + email summaries for biggest movers

---

## 👋 Credits
Built by @yourname — inspired by prediction markets, CMC, and the future of market intelligence.
