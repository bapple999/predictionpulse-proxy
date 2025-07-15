"""
Shared helpers for every ingestion script.
"""
import os
import requests
import itertools
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
