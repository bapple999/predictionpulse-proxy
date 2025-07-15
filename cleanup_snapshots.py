#!/usr/bin/env python
"""Delete old market snapshots from Supabase.

Usage:
  python cleanup_snapshots.py <ISO8601 timestamp>

A cutoff timestamp can also be provided via the SNAPSHOT_CUTOFF environment
variable.
"""

import os
import sys
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

def main(cutoff: str) -> None:
    url = f"{SUPABASE_URL}/rest/v1/market_snapshots"
    r = requests.delete(url, headers=HEADERS,
                        params={"timestamp": f"lt.{cutoff}"},
                        timeout=30)
    if r.status_code not in (200, 204):
        print(f"❌ delete failed {r.status_code}: {r.text[:200]}")
    else:
        print(f"✅ deleted snapshots older than {cutoff}")

if __name__ == "__main__":
    cutoff = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SNAPSHOT_CUTOFF")
    if not cutoff:
        print("Provide cutoff timestamp as argument or SNAPSHOT_CUTOFF env var")
        sys.exit(1)
    main(cutoff)
