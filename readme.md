# Prediction Pulse Ingestion Jobs

This project uses GitHub Actions to run two types of ingestion scripts for each data source (Polymarket and Kalshi):

---

## 🔁 Script Structure

### Polymarket

| Script                        | Purpose                                 | Frequency        |
| ----------------------------- | --------------------------------------- | ---------------- |
| `polymarket_fetch.py`         | Fetches full metadata, prices, outcomes | Daily @ 5:00 UTC |
| `polymarket_update_prices.py` | Updates prices and volumes only         | Every 5 minutes  |

### Kalshi

| Script                    | Purpose                            | Frequency        |
| ------------------------- | ---------------------------------- | ---------------- |
| `kalshi_fetch.py`         | Fetches full metadata + event info | Daily @ 5:00 UTC |
| `kalshi_update_prices.py` | Updates prices and outcomes only   | Every 5 minutes  |

---

## ⚙️ GitHub Action Workflows

### `.github/workflows/polymarket.yml`

Runs:

* `polymarket_fetch.py` daily
* `polymarket_update_prices.py` every 5 minutes

### `.github/workflows/kalshi.yml`

Runs:

* `kalshi_fetch.py` daily
* `kalshi_update_prices.py` every 5 minutes

All workflows:

* Use `python-version: 3.11`
* Run `pip install -r requirements.txt`
* Inject secrets:

  * `SUPABASE_URL`
  * `SUPABASE_SERVICE_ROLE_KEY`
  * `KALSHI_API_KEY` (Kalshi only)

---

## ✅ Supabase Tables

| Table              | Source Data                    |
| ------------------ | ------------------------------ |
| `markets`          | Full market metadata           |
| `market_snapshots` | Price + liquidity over time    |
| `market_outcomes`  | Outcome-level pricing (Yes/No) |

---

## 📌 Tips

* Use `workflow_dispatch` for manual runs.
* Keep long fetches (e.g. Polymarket pagination) in the daily jobs.
* Use short lightweight price-only jobs for frequent updates.

---

For help or to expand the structure (alerts, summaries, etc), check the `scripts/` folder or ask in `/docs/dev-notes.md`.
