"""
Shared helpers for every ingestion script.
"""
import os, requests, itertools

SUPABASE_URL  = os.environ["SUPABASE_URL"]
SERVICE_KEY   = os.environ["SUPABASE_SERVICE_ROLE_KEY"]    # long service key

# Sent on every REST call
BASE_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    # merge‑duplicates => upsert
    "Prefer":        "return=minimal,resolution=merge-duplicates"
}

def _chunked(iterable, size=500):
    """Yield successive *size*-item chunks."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            break
        yield batch

def insert_to_supabase(table: str, rows: list, conflict_key: str = "market_id"):
    """
    Bulk‑UPSERT *rows* (list[dict]) into Supabase table *table*.
    Uses merge‑duplicates so reruns are idempotent.
    """
    if not rows:
        print(f"⚠️  no data for {table}")
        return

    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={conflict_key}"
    for chunk in _chunked(rows):
        r = requests.post(url, headers=BASE_HEADERS, json=chunk, timeout=30)
        if r.status_code not in (201, 204):
            print(f"❌ {table} → {r.status_code}: {r.text[:200]}")
        else:
            print(f"✅ {table}: inserted {len(chunk)} rows")
