# kalshi_fetch.py – hourly metadata + snapshot loader for Kalshi

import os
import requests
from datetime import datetime
from common import insert_to_supabase  # shared helper

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SERVICE_KEY  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
SUPA_HEADERS = {
    'apikey': SERVICE_KEY,
    'Authorization': f"Bearer {SERVICE_KEY}",
    'Content-Type': 'application/json',
}

# Kalshi API endpoints
EVENTS_URL  = 'https://api.elections.kalshi.com/trade-api/v2/events'
MARKETS_URL = 'https://api.elections.kalshi.com/trade-api/v2/markets'
HEADERS_KALSHI = {'Authorization': f"Bearer {os.environ.get('KALSHI_API_KEY')}"}

# ───────── helpers ─────────

def safe_ts(val):
    """Ensure timestamp is a valid ISO string or None."""
    return val if val and val.strip() else None

# ───────── fetch events ─────────

def fetch_events() -> dict:
    """Fetch all Kalshi events and index by ticker."""
    print('📡 Fetching Kalshi events…', flush=True)
    resp = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15)
    resp.raise_for_status()
    evs = resp.json().get('events', [])
    print(f'🔍 Retrieved {len(evs)} events', flush=True)
    # index on event TICKER
    index = {}
    for e in evs:
        key = e.get('ticker') or e.get('event_ticker')
        if key:
            index[key] = e
    return index

# ───────── fetch markets in pages ─────────

def fetch_all_markets(limit: int = 1000) -> list:
    """Fetch all markets via offset pagination with duplicate detection."""
    print('📡 Fetching Kalshi markets (paged)…', flush=True)
    markets = []
    seen = set()
    offset = 0

    while True:
        resp = requests.get(
            MARKETS_URL,
            headers=HEADERS_KALSHI,
            params={'limit': limit, 'offset': offset},
            timeout=15
        )
        if resp.status_code in (502, 504):
            print(f'⚠️ Kalshi 50x at offset {offset}, stopping', flush=True)
            break
        resp.raise_for_status()

        batch = resp.json().get('markets', [])
        if not batch:
            break

        tickers = [m.get('ticker') for m in batch if m.get('ticker')]
        if any(t in seen for t in tickers):
            print(f'🔒 Duplicate page at offset {offset}, stopping', flush=True)
            break
        seen.update(tickers)

        markets.extend(batch)
        offset += limit
        print(f'⏱ Retrieved {len(batch):4} markets (offset {offset})', flush=True)

        if len(batch) < limit:
            break

    print(f'🔍 Total markets fetched: {len(markets)}', flush=True)
    return markets

# ───────── main logic ─────────

def main():
    # 1) Fetch events and markets
    events      = fetch_events()
    raw_markets = fetch_all_markets()

    # 2) Prepare for ingestion
    print(f'🏆 Markets to ingest: {len(raw_markets)}', flush=True)
    now_ts = datetime.utcnow().isoformat() + 'Z'
    rows_m, rows_s, rows_o = [], [], []

    for m in raw_markets:
        ticker = m.get('ticker')
        if not ticker:
            continue

        # Match event metadata
        ev = events.get(m.get('event_ticker')) or {}

        # ─ Market row ─
        rows_m.append({
            'market_id':          ticker,
            'market_name':        m.get('title') or m.get('description') or '',
            'market_description': m.get('description') or '',
            'event_name':         ev.get('title') or '',
            'event_ticker':       m.get('event_ticker') or '',
            'expiration':         safe_ts(m.get('expiration')),
            'tags':               m.get('tags', []),
            'source':             'kalshi',
            'status':             m.get('status') or '',
        })

        # ─ Snapshot row ─
        yes = m.get('yes_bid')
        no  = m.get('no_bid')
        prob = ((yes + (1 - no)) / 2) if yes is not None and no is not None else None

        rows_s.append({
            'market_id':  ticker,
            'price':      round(prob, 4) if prob is not None else None,
            'yes_bid':    yes,
            'no_bid':     no,
            'volume':     m.get('volume'),
            'liquidity':  m.get('open_interest'),
            'timestamp':  now_ts,
            'source':     'kalshi',
        })

        # ─ Outcome rows ─
        if prob is not None:
            rows_o.extend([
                {
                    'market_id': ticker,
                    'outcome_name': 'Yes',
                    'price': yes,
                    'volume': None,
                    'timestamp': now_ts,
                    'source': 'kalshi',
                },
                {
                    'market_id': ticker,
                    'outcome_name': 'No',
                    'price': 1 - no,
                    'volume': None,
                    'timestamp': now_ts,
                    'source': 'kalshi',
                },
            ])

    # 3) Write to Supabase
    print('💾 Upserting markets…', flush=True)
    insert_to_supabase('markets', rows_m)
    print('💾 Writing snapshots…', flush=True)
    insert_to_supabase('market_snapshots', rows_s, conflict_key=None)
    print('💾 Writing outcomes…', flush=True)
    insert_to_supabase('market_outcomes', rows_o, conflict_key=None)
    print(f'✅ Markets {len(rows_m)} | Snapshots {len(rows_s)} | Outcomes {len(rows_o)}', flush=True)

# ───────── entry point ─────────
if __name__ == '__main__':
    main()
