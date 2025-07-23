# 📊 Prediction Pulse — Ingestion Pipeline

*Fast, idempotent loaders for Kalshi & Polymarket → Supabase*

[![Kalshi Full Fetch](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_fetch.yml)
[![Kalshi Price Updates](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_update.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_update.yml)
[![Polymarket Full Fetch](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket-fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket-fetch.yml)
[![Polymarket Price Updates](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket_price_updates.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket_price_updates.yml)

## 🎯 Purpose

Prediction Pulse is an open-source project that aggregates prediction market data (Kalshi, Polymarket) and surfaces real-time, category-specific insights — enabling traders, analysts, and curious observers to understand market sentiment and react quickly.

The platform aims to:

- Aggregate markets from multiple sources in one place
- Show the most active markets by volume and volatility
- Break down trends by category (Economics, Politics, Sports, Pop Culture)
- Use LLMs to automatically summarize major market movements and tie them to real-world news

---

## 🚀 Quick‑start (local)

```bash
# Clone & install
 git clone https://github.com/yourname/predictionpulse-proxy.git
 cd predictionpulse-proxy
 pip install -r requirements.txt

# Configure secrets
 cp .env.example .env      # fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, KALSHI_API_KEY, POLYMARKET_API_KEY
                           # (optionally) POLYMARKET_CLOB_URL & POLYMARKET_TRADES_URL if using a proxy

# Run once to verify
 python kalshi_fetch.py               # daily metadata load
 python kalshi_update_prices.py       # single price snapshot
 python kalshi_ws.py                  # live ticker feed via WebSocket
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
├── kalshi_ws.py                 # stream ticker_v2 via WebSocket
├── polymarket_fetch.py           # daily full‑market load
├── polymarket_update_prices.py   # 5‑minute snapshots
├── market_news_summary.py        # summarize big movers
├── requirements.txt
├── README.md
├── webapp/                      # React front-end powered by Vite
│   ├── App.jsx
│   ├── components/
│   ├── pages/
│   └── ...
└── .github/
    └── workflows/
        ├── kalshi_fetch.yml
        ├── kalshi_update.yml
        ├── polymarket-fetch.yml
        └── polymarket_price_updates.yml
```

---

## 🤖 AI-Powered Insights

The `market_news_summary.py` script uses GPT-4 (via OpenAI API) to:

- Detect the biggest movers across all markets
- Summarize why the market may have moved (based on external news scraping)
- Generate concise headlines for users or Discord/web notifications

Planned: deeper summarization models that track *why* probabilities shift over time (e.g., "CPI odds fell after Fed comments").

## 🔑 Required environment variables

| Var                         | Purpose                               |
| --------------------------- | ------------------------------------- |
| `SUPABASE_URL`              | e.g. `https://abcde.supabase.co`      |
| `SUPABASE_SERVICE_ROLE_KEY` | long service key (server‑side only)   |
| `KALSHI_API_KEY`            | Kalshi personal API token             |
| `KALSHI_API_BASE`          | (optional) override base API URL      |
| `KALSHI_WS_URL`             | (optional) override WebSocket endpoint |
| `POLYMARKET_API_KEY`        | (optional) higher quota for Gamma API |
| `POLYMARKET_GAMMA_URL`      | (optional) override for Gamma API     |
| `POLYMARKET_EVENTS_URL`     | (optional) override for events API    |
| `POLYMARKET_CLOB_URL`       | (optional) proxy base for CLOB API    |
| `POLYMARKET_TRADES_URL`     | (optional) proxy base for trades API  |

See **`.env.example`** for a template and add them to **`.env`** for local runs. Store them in **GitHub Secrets** for CI.

The default Kalshi API endpoint is `https://api.elections.kalshi.com/trade-api/v2`. Use
`KALSHI_API_BASE` if you need to point to a different host.

### Front-end config

The React app in `webapp/` uses just two environment variables:
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. For local development:


cp webapp/.env.example webapp/.env
# edit VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

On Netlify, set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in your
site settings. They will be injected at build time via `import.meta.env`.

The old static demo under `public/` still supports a `config.js` file for
backwards compatibility. It now imports Chart.js as an ES module so you can
deploy with a strict CSP and omit `'unsafe-eval'`.

### Troubleshooting

If the page fails to load and the browser console shows errors like:

```
The source list for the Content Security Policy directive 'connect-src' contains an invalid source: 'https://YOUR_PROJECT.supabase.co'.
```

then `config.js` was not found and `netlify.toml` still contained the placeholder project URL.

check that `VITE_SUPABASE_URL` in your Netlify settings matches your actual
Supabase project URL. The React app will fail if these variables are missing.



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

SQL definitions live in [`schema.sql`](schema.sql).

* **`events`** — groups related markets (primary key `event_id`)
* **`markets`** — static metadata (primary key `market_id`)
* **`market_prices`** — daily price records and change metrics
* **`market_snapshots`** — price / volume time‑series
* **`market_outcomes`** — outcome‑level bids (Yes/No, Team A/Team B, etc.)

`market_snapshots.market_id` and `market_outcomes.market_id` both reference
`markets.market_id`.
The `tags` column is `jsonb`; just pass a Python list (`["econ", "CPI"]`).

The `latest_snapshots` view returns the most recent snapshot per market and the
timestamp of the first snapshot as `start_date`. The front‑end queries columns
`market_id`, `source`, `market_name`, `expiration`, `start_date`, `tags`,
`price`, `volume`, `dollar_volume`, `liquidity` and `timestamp`.

## 🖥 Frontend web app

The `webapp/` directory contains a small React app built with [Vite](https://vitejs.dev/).
Run `npm install` inside that folder. For a strict Content Security Policy you should
build the app with `npm run build` and then preview it using `npm run preview`.

### Key Features

- Top Markets: ranked by trading volume and movement
- Category Filters: quickly explore Sports, Politics, Economics, etc.
- Market Detail Page: shows real-time price, volume, and resolution info
- AI Insights: auto-generated explanations for major movers
- Responsive UI for desktop and mobile

### Netlify

Netlify doesn't run `npm install` automatically because the repo root lacks a
`package.json`. The `netlify.toml` build command therefore installs the webapp
dependencies explicitly:

```toml
[build]
  command = "npm ci --prefix webapp && npm run --prefix webapp build"
  publish = "webapp/dist"
```

## 🌐 Live Demo

[View the app](https://your-netlify-site.netlify.app)

Home screen shows the top 10 markets by volume, broken down by category. Users can drill down into each market to explore historical movement and view AI-generated insights.

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
