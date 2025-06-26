# 📊 Prediction Pulse — Ingestion Pipeline

*Fast, idempotent loaders for Kalshi & Polymarket → Supabase*

[![Kalshi Full Fetch](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/kalshi_fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/kalshi_fetch.yml)
[![Kalshi Price Updates](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/kalshi_update.yml/badge.svg)](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/kalshi_update.yml)
[![Polymarket Full Fetch](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/polymarket-fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/polymarket-fetch.yml)
[![Polymarket Price Updates](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/polymarket_price_updates.yml/badge.svg)](https://github.com/yourname/predictionpulse-ingestion/actions/workflows/polymarket_price_updates.yml)

---

## 🚀 Quick‑start (local)

```bash
# Clone & install
 git clone https://github.com/yourname/predictionpulse-ingestion.git
 cd predictionpulse-ingestion
 pip install -r requirements.txt

# Configure secrets
 cp .env.example .env      # fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, KALSHI_API_KEY, POLYMARKET_API_KEY

# Run once to verify
 python kalshi_fetch.py               # daily metadata load
 python kalshi_update_prices.py       # single price snapshot
 python market_news_summary.py        # summarize movers w/ news
```

*Requires Python 3.11+*

---

## 🗂 Project layout

```
.
├── common.py                     # shared insert_to_supabase helper
├── kalshi_fetch.py               # daily full‑market load
├── kalshi_update_prices.py       # 5‑minute snapshots
├── polymarket_fetch.py           # daily full‑market load
├── polymarket_update_prices.py   # 5‑minute snapshots
├── market_news_summary.py        # summarize big movers
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        ├── kalshi_fetch.yml
        ├── kalshi_update.yml
        ├── polymarket-fetch.yml
        └── polymarket_price_updates.yml
```

---

## 🔑 Required environment variables

| Var                         | Purpose                               |
| --------------------------- | ------------------------------------- |
| `SUPABASE_URL`              | e.g. `https://abcde.supabase.co`      |
| `SUPABASE_SERVICE_ROLE_KEY` | long service key (server‑side only)   |
| `KALSHI_API_KEY`            | Kalshi personal API token             |
| `POLYMARKET_API_KEY`        | (optional) higher quota for Gamma API |

Add them to **`.env`** for local runs and **GitHub Secrets** for CI.

### Front-end config

The demo page in `public/` reads credentials from `public/config.js`. Create it
from the example and fill in your values:

```bash
cp public/config.example.js public/config.js
# edit with your SUPABASE_URL and anon key
```

`config.js` is ignored by git so your key won't be committed.

---

## 🔃 Scheduled jobs

| Workflow file                  | Script                               | Cron          |
| ------------------------------ | ------------------------------------ | ------------- |
| `kalshi_fetch.yml`             | `python kalshi_fetch.py`             | `0 5 * * *`   |
| `kalshi_update.yml`            | `python kalshi_update_prices.py`     | `*/5 * * * *` |
| `polymarket-fetch.yml`         | `python polymarket_fetch.py`         | `0 6 * * *`   |
| `polymarket_price_updates.yml` | `python polymarket_update_prices.py` | `*/5 * * * *` |

Full‑fetch jobs rebuild metadata once a day; lightweight update jobs keep quotes fresh every five minutes without hammering the APIs.

---

## 🗄 Supabase schema (jsonb ≈ arrays)

* **`markets`** — static metadata
* **`market_snapshots`** — price / volume time‑series
* **`market_outcomes`** — outcome‑level bids (Yes/No, Team A/Team B, etc.)

The `tags` column is `jsonb`; just pass a Python list (`["econ","CPI"]`).

---

## 🛣 Roadmap

* [ ] Add `market_resolutions` table (winner + resolved price)
* [ ] Discord webhook for moves >5 ppt in 24 h
* [ ] Historical chart endpoint

---

## ⚠️ Disclaimer

All data is provided “as is” for informational purposes only and **is not financial advice**.

---

## 📝 License

MIT
