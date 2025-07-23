"""
Shared helpers for every ingestion script.
"""
import os
try:
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled in tests
    class _RequestsPlaceholder:
        """Minimal placeholder so tests can monkeypatch ``requests``."""

        RequestException = Exception

        def get(self, *a, **kw):  # pragma: no cover - network disabled
            raise RuntimeError(
                "The 'requests' library is required for network operations"
            )

        def post(self, *a, **kw):  # pragma: no cover - network disabled
            raise RuntimeError(
                "The 'requests' library is required for network operations"
            )

    requests = _RequestsPlaceholder()
import itertools
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY")   # long service key

if not SUPABASE_URL or not SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

BASE_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    # merge‑duplicates → upsert (only when an on_conflict key is supplied)
    "Prefer":        "return=minimal,resolution=merge-duplicates",
}

def _chunked(iterable, size: int = 500):
    """Yield successive *size*-item chunks."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            break
        yield batch

def request_json(url: str, *, headers=None, params=None,
                 tries: int = 3, backoff: float = 1.5, timeout: int = 20):
    """Return JSON response from *url* with simple retries."""
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"request failed ({i + 1}/{tries}) {url}: {e}")
            if i == tries - 1:
                return None
            time.sleep(backoff * (2 ** i))

def insert_to_supabase(table: str, rows: list, conflict_key: str | None = "market_id"):
    """
    Bulk‑insert / upsert *rows* into Supabase table *table*.

    - If `conflict_key` is a string  → adds ?on_conflict=<key> for UPSERT behaviour.
    - If `conflict_key` is None      → plain INSERT (no unique‑key requirement).
    """
    if not rows:
        print(f"⚠️  no data for {table}")
        return

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if conflict_key:
        url += f"?on_conflict={conflict_key}"

    for chunk in _chunked(rows):
        r = requests.post(url, headers=BASE_HEADERS, json=chunk, timeout=30)
        if r.status_code not in (201, 204):
            print(f"❌ {table} → {r.status_code}: {r.text[:150]}")
        else:
            print(f"✅ {table}: inserted {len(chunk)} rows")

# ───────────────── Polymarket helpers
# Allow overriding the default endpoints via environment variables. This makes
# it possible to point the loader at a custom proxy when direct network access
# is restricted.
GAMMA_URL = os.environ.get(
    "POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com/markets"
)
CLOB_URL = os.environ.get(
    "POLYMARKET_CLOB_URL", "https://clob.polymarket.com/markets/{}"
)
TRADES_URL = os.environ.get(
    "POLYMARKET_TRADES_URL", "https://clob.polymarket.com/markets/{}/trades"
)
EVENTS_URL = os.environ.get(
    "POLYMARKET_EVENTS_URL", "https://gamma-api.polymarket.com/events"
)


def fetch_gamma():
    """Return a list of all markets from Polymarket's Gamma API."""
    headers = {}
    api_key = os.environ.get("POLYMARKET_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    r = requests.get(GAMMA_URL, headers=headers, timeout=15)
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict) and "markets" in j:
        return j["markets"]
    return j


def fetch_events(limit: int = 250, max_pages: int = 10, **filters):
    """Return a list of events from Polymarket's Gamma API."""
    headers = {}
    api_key = os.environ.get("POLYMARKET_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    events = []
    offset = 0
    for _ in range(max_pages):
        params = {"limit": limit, "offset": offset}
        params.update(filters)
        r = requests.get(EVENTS_URL, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        j = r.json()
        batch = j.get("events") if isinstance(j, dict) else j
        if not batch:
            break
        events.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return events


def fetch_clob(mid: str, slug: str | None = None):
    """Fetch order book details by market ID or slug."""
    for ident in filter(None, [mid, slug]):
        try:
            r = requests.get(CLOB_URL.format(ident), timeout=8)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            continue
    return None


def last24h_stats(mid: str):
    """Return (dollar_volume, trade_count, vwap) for the past 24h."""
    try:
        r = requests.get(TRADES_URL.format(mid), timeout=8)
        if r.status_code == 404:
            return 0.0, 0, None
        r.raise_for_status()
        from datetime import datetime, timedelta
        from dateutil import parser
        cutoff = datetime.utcnow() - timedelta(hours=24)
        vol_d = 0.0
        vol_ct = 0
        for t in r.json().get("trades", []):
            ts = parser.parse(t.get("timestamp"))
            if ts >= cutoff:
                size = t.get("amount")
                price = t.get("price") / 100
                vol_ct += size
                vol_d += size * price
        vwap = round(vol_d / vol_ct, 4) if vol_ct else None
        return round(vol_d, 2), vol_ct, vwap
    except Exception:
        return 0.0, 0, None
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_stats_concurrent(market_ids, fetch_fn):
    """Fetch trade stats concurrently using *fetch_fn*.

    Args:
        market_ids: iterable of market identifiers
        fetch_fn: function taking a market_id and returning stats
    Returns:
        (results, failed) where results is a list of (market_id, stats)
        and failed is a list of market_ids that raised exceptions.
    """
    results = []
    failed = []
    if not market_ids:
        return results, failed
    workers = min(8, len(market_ids))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_fn, mid): mid for mid in market_ids}
        for fut in as_completed(futures):
            mid = futures[fut]
            try:
                stats = fut.result()
                results.append((mid, stats))
            except Exception as e:
                print(f"⚠️ stats fetch failed for {mid}: {e}")
                failed.append(mid)
    return results, failed


def fetch_price_24h_ago(market_id: str) -> float | None:
    """Return the most recent price from 24 hours ago for *market_id*."""
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
    url = f"{SUPABASE_URL}/rest/v1/market_snapshots"
    params = {
        "select": "price",
        "market_id": f"eq.{market_id}",
        "timestamp": f"lt.{since}",
        "order": "timestamp.desc",
        "limit": 1,
    }
    try:
        r = requests.get(url, headers=BASE_HEADERS, params=params, timeout=10)
        r.raise_for_status()
        rows = r.json()
        return rows[0]["price"] if rows else None
    except Exception:
        return None
