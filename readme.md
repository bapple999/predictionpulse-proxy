# 📊 Prediction Pulse — Ingestion Pipeline

*Fast, idempotent loaders for Kalshi & Polymarket → Supabase*

[![Kalshi Markets](https://github.com/yourname/prediction-pulse-ingestion/actions/workflows/kalshi.yml/badge.svg)](https://github.com/yourname/prediction-pulse-ingestion/actions/workflows/kalshi.yml)
[![Polymarket Markets](https://github.com/yourname/prediction-pulse-ingestion/actions/workflows/polymarket.yml/badge.svg)](https://github.com/yourname/prediction-pulse-ingestion/actions/workflows/polymarket.yml)

---

## 🚀 Quick‑start (local)

```bash
# clone & install
git clone https://github.com/yourname/prediction‑pulse‑ingestion.git
cd prediction‑pulse‑ingestion
cp .env.example .env                # add the three keys below
pip install -r requirements.txt

# one‑off test runs
python scripts/kalshi_fetch.py       # full Kalshi load
python scripts/kalshi_update_prices.py  # single price snapshot
```

*Requires **Python 3.11+***.

---

## 🔑 Required environment variables

| Var                         | Purpose                                                |
| --------------------------- | ------------------------------------------------------ |
| `SUPABASE_URL`              | e.g. `https://abcde.supabase.co`                       |
| `SUPABASE_SERVICE_ROLE_KEY` | Long service key (server‑side only)                    |
| `KALSHI_API_KEY`            | Personal Kalshi API token                              |
| `POLYMARKET_API_KEY`        | (optional) only if you hit the private Gamma endpoints |

Add them **once** in both `.env` (for local runs) **and** your GitHub Secrets.

---

## 📁 Project Structure

```bash
├── scripts/
│   ├── polymarket_fetch.py           # Daily full fetch
│   ├── polymarket_update_prices.py   # 5‑min snapshots
│   ├── kalshi_fetch.py               # Daily full fetch + events
│   └── kalshi_update_prices.py       # 5‑min snapshots
│
├── .github/
│   └── workflows/
│       ├── polymarket.yml
│       └── kalshi.yml
│
├── requirements.txt
└── README.md
```

---

## 🔃 Scheduled Jobs

| Workflow                 | Script                        | Cron          | Rows / run       |
| ------------------------ | ----------------------------- | ------------- | ---------------- |
| **Kalshi Markets**       | `kalshi_fetch.py`             | `0 2 * * *`   | \~1 000 markets  |
| **Kalshi Snapshots**     | `kalshi_update_prices.py`     | `*/5 * * * *` | \~10 k snapshots |
| **Polymarket Markets**   | `polymarket_fetch.py`         | `0 3 * * *`   | similar          |
| **Polymarket Snapshots** | `polymarket_update_prices.py` | `*/5 * * * *` | similar          |

*Full‑fetch jobs rebuild metadata; snapshot jobs keep prices fresh without hammering the APIs.*

---

## 🗄 Supabase Schema (simplified)

### `markets`  — core metadata

```jsonc
{
  "market_id": "string",
  "market_name": "string",
  "description": "string",
  "event_name": "string",
  "expiration": "timestamp",
  "tags": ["string"],  // jsonb array
  "source": "kalshi | polymarket",
  "status": "active | closed | resolved"
}
```

### `market_snapshots`  — price history

```jsonc
{
  "market_id": "string",
  "price": 0.53,
  "volume": 12000,
  "liquidity": 45000,
  "timestamp": "timestamp",
  "source": "kalshi | polymarket"
}
```

### `market_outcomes`  — YES/NO legs

```jsonc
{
  "market_id": "string",
  "outcome_name": "Yes | No",
  "price": 0.57,
  "timestamp": "timestamp",
  "source": "kalshi | polymarket"
}
```

> **Note**  `tags` is stored as **`jsonb`**. Send `["economics","CPI"]`, not a Postgres array literal.

---

## 🛣 Roadmap

* [ ] Add `market_resolutions` table (winner + close price)
* [ ] Webhook → Discord for >5 ppt moves
* [ ] AI‑generated “TL;DR why it moved” summaries

---

### ⚠️ Disclaimer

Data is provided “as is”; **not financial advice**.

### 📝 License

MIT
