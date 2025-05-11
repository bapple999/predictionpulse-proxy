# kalshi_fetch.py – updated to paginate beyond 1000 safely

import os
import requests
from datetime import datetime
from common import insert_to_supabase

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
HEADERS_KALSHI = {'Authorization': f"Bearer {os.environ.get('KALSHI_API_KEY')}"}

EVENTS_URL = 'https://api.elections.kalshi.com/trade-api/v2/events'
MARKETS_URL = 'https://api.elections.kalshi.com/trade-api/v2/markets'

def safe_ts(val):
    return val if val and val.strip() else None

def fetch_events():
    print('📡 Fetching Kalshi events…', flush=True)
    resp = requests.get(EVENTS_URL, headers=HEADERS_KALSHI, timeout=15)
    resp.raise_for_status()
    events = resp.json().get('events', [])
    print(f'🔍 Retrieved {len(events)} events', flush=True)
    return {e.get('ticker'): e for e in events if e.get('ticker')}

def fetch_all_markets(limit=1000, max_pages=50):
    print('📡 Fetching Kalshi markets (paged)…', flush=True)
    markets, seen, offset, pages = [], set(), 0, 0
    while pages < max_pages:
        resp = requests.get(
            MARKETS_URL,
            headers=HEADERS_KALSHI,
            params={'limit': limit, 'offset': offset},
            timeout=15
        )
        resp.raise_for_status()
        batch = resp.json().get('markets', [])
        if not batch:
            break

        new_batch = [m for m in batch if m.get('ticker') not in seen]
        seen.update(m.get('ticker') for m in new_batch if m.get('ticker'))
        markets.extend(new_batch)
        offset += limit
        pages += 1
        print(f'⏱ Retrieved {len(new_batch):4} new markets (offset {offset})', flush=True)

        if len(batch) < limit:
            break
    print(f'🔍 Total markets fetched: {len(markets)}', flush=True)
    return markets

def main():
    events = fetch_events()
    raw_markets = fetch_all_markets()
    print(f'🏆 Markets to ingest: {len(raw_markets)}', flush=True)

    now_ts = datetime.utcnow().isoformat() + 'Z'
    rows_m, rows_s, rows_o = [], [], []

    for m in raw_markets:
        ticker = m.get('ticker')
        if not ticker:
            continue

        ev = events.get(m.get('event_ticker')) or {}
        yes = m.get('yes_bid')
        no = m.get('no_bid')
        prob = ((yes + (1 - no)) / 2) if yes is not None and no is not None else None

        rows_m.append({
            'market_id': ticker,
            'market_name': m.get('title') or m.get('description') or '',
            'market_description': m.get('description') or '',
            'event_name': ev.get('title') or ev.get('name') or '',
            'event_ticker': m.get('event_ticker') or '',
            'expiration': safe_ts(m.get('expiration')),
            'tags': m.get('tags') if m.get('tags') is not None else [],
            'source': 'kalshi',
            'status': m.get('status') or '',
        })

        rows_s.append({
            'market_id': ticker,
            'price': round(prob, 4) if prob is not None else None,
            'yes_bid': yes,
            'no_bid': no,
            'volume': m.get('volume'),
            'liquidity': m.get('open_interest'),
            'timestamp': now_ts,
            'source': 'kalshi',
        })

        if yes is not None:
            rows_o.append({
                'market_id': ticker,
                'outcome_name': 'Yes',
                'price': yes,
                'volume': None,
                'timestamp': now_ts,
                'source': 'kalshi',
            })
        if no is not None:
            rows_o.append({
                'market_id': ticker,
                'outcome_name': 'No',
                'price': 1 - no,
                'volume': None,
                'timestamp': now_ts,
                'source': 'kalshi',
            })

    print('💾 Upserting markets…', flush=True)
    insert_to_supabase('markets', rows_m)
    print('💾 Writing snapshots…', flush=True)
    insert_to_supabase('market_snapshots', rows_s, conflict_key=None)
    print('💾 Writing outcomes…', flush=True)
    insert_to_supabase('market_outcomes', rows_o, conflict_key=None)
    print(f'✅ Markets {len(rows_m)} | Snapshots {len(rows_s)} | Outcomes {len(rows_o)}', flush=True)

if __name__ == '__main__':
    main()
