# 📊 Prediction Pulse — Ingestion Pipeline

*Fast, idempotent loaders for Kalshi & Polymarket → Supabase*

[![Kalshi Full Fetch](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_fetch.yml)
[![Kalshi Price Updates](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_update.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/kalshi_update.yml)
[![Polymarket Full Fetch](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket-fetch.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket-fetch.yml)
[![Polymarket Price Updates](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket_price_updates.yml/badge.svg)](https://github.com/yourname/predictionpulse-proxy/actions/workflows/polymarket_price_updates.yml)

---

## 🚀 Quick‑start (local)

```bash
# Clone & install
 git clone https://github.com/yourname/predictionpulse-proxy.git
 cd predictionpulse-proxy
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

See **`.env.example`** for a template and add them to **`.env`** for local runs. Store them in **GitHub Secrets** for CI.

### Front-end config

The React app in `webapp/` uses just two environment variables:
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. For local development:

```bash
cp webapp/.env.example webapp/.env
# edit VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
```

On Netlify, set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in your
site settings. They will be injected at build time via `import.meta.env`.

The old static demo under `public/` still supports a `config.js` file for
backwards compatibility.

### Troubleshooting

If the page fails to load and the browser console shows errors like:

```
The source list for the Content Security Policy directive 'connect-src' contains an invalid source: 'https://YOUR_PROJECT.supabase.co'.
```

check that `VITE_SUPABASE_URL` in your Netlify settings matches your actual
Supabase project URL. The React app will fail if these variables are missing.

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

## 🖥 Frontend web app

The `webapp/` directory contains a small React app built with [Vite](https://vitejs.dev/).
Run `npm install` inside that folder and `npm run dev` to start a local preview.

### Netlify

Netlify doesn't run `npm install` automatically because the repo root lacks a
`package.json`. The `netlify.toml` build command therefore installs the webapp
dependencies explicitly:

```toml
[build]
  command = "npm ci --prefix webapp && npm run --prefix webapp build"
  publish = "webapp/dist"
```

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
