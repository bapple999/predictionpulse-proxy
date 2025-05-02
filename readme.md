# 📊 Prediction Pulse Ingestion Pipeline

This repository powers the data ingestion for **Prediction Pulse**, aggregating market data from Polymarket and Kalshi into a Supabase database for analytics, dashboards, and prediction market insights.

---

## 📁 Project Structure

```bash
├── scripts/
│   ├── polymarket_fetch.py           # Daily full fetch
│   ├── polymarket_update_prices.py   # Frequent price updates
│   ├── kalshi_fetch.py               # Daily full fetch + events
│   └── kalshi_update_prices.py       # Frequent price updates
│
├── .github/
│   └── workflows/
│       ├── polymarket.yml
│       └── kalshi.yml
│
├── requirements.txt
└── README.md
```

---

## 🔄 Workflow Overview

### Polymarket

| Script                        | Function                                                                                       | Frequency        |
| ----------------------------- | ---------------------------------------------------------------------------------------------- | ---------------- |
| `polymarket_fetch.py`         | Fetches all market metadata, expiration, tags, and real-time price data from Gamma & CLOB APIs | Daily @ 5:00 UTC |
| `polymarket_update_prices.py` | Refreshes prices, volume, liquidity only via CLOB                                              | Every 5 minutes  |

### Kalshi

| Script                    | Function                                                                                   | Frequency        |
| ------------------------- | ------------------------------------------------------------------------------------------ | ---------------- |
| `kalshi_fetch.py`         | Fetches all market metadata and event info, price bids, and calculates implied probability | Daily @ 5:00 UTC |
| `kalshi_update_prices.py` | Refreshes current prices and outcomes only                                                 | Every 5 minutes  |

---

## ⚙️ GitHub Actions

Each workflow uses environment variables and GitHub secrets:

### Common Steps in Workflows:

* Checkout repo
* Set up Python 3.11
* Install dependencies via `requirements.txt`
* Set secrets via environment variables

### Required Secrets

* `SUPABASE_URL`
* `SUPABASE_SERVICE_ROLE_KEY`
* `KALSHI_API_KEY` (only for Kalshi scripts)

### Files

* `.github/workflows/polymarket.yml`
* `.github/workflows/kalshi.yml`

Each workflow includes `workflow_dispatch` for manual runs.

---

## 🗃 Supabase Table Schema

### `markets`

Stores core metadata and event descriptions

```json
{
  "market_id": "string",
  "market_name": "string",
  "description": "string",
  "event_name": "string",
  "expiration": "timestamp",
  "tags": ["string"],
  "source": "kalshi" | "polymarket",
  "status": "active" | "closed" | "resolved"
}
```

### `market_snapshots`

Price, volume, and liquidity over time

```json
{
  "market_id": "string",
  "price": float,
  "volume": float,
  "liquidity": float,
  "timestamp": "timestamp",
  "source": "kalshi" | "polymarket"
}
```

### `market_outcomes`

Outcome-level pricing (e.g., Yes/No)

```json
{
  "market_id": "string",
  "outcome_name": "Yes" | "No",
  "price": float,
  "timestamp": "timestamp",
  "source": "kalshi" | "polymarket"
}
```

---

## 📌 Best Practices

* Use `fetch.py` jobs for complete metadata refresh (daily only)
* Use `update_prices.py` jobs for frequent lightweight updates
* Monitor API usage to avoid rate limiting (especially Polymarket CLOB)
* Store intermediate results locally for development or test runs
* Keep Supabase `Prefer: return=minimal` for performance

---

## 🚀 Future Ideas

* Add webhook alerts for big market movements
* AI-generated news summaries for major shifts
* Historical charts per market ID
* Dashboard pages per source
* Market metadata archive or freeze history

---

For dev notes, see `/docs/dev-notes.md` (to be created).

Questions? Open an issue or contact the maintainer.
