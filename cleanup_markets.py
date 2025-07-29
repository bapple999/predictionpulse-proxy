#!/usr/bin/env python
"""Cleanup old market snapshots and inactive markets from Supabase.

Usage:
  python cleanup_markets.py 2024-05-01T00:00:00Z

If no timestamp argument is supplied, ``SNAPSHOT_CUTOFF`` is read from the
environment. Set ``DELETE_LOW_VOLUME=1`` or pass ``--low-volume`` to also
remove low‑volume markets (not implemented via REST API).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    # return deleted rows so we can count them
    "Prefer": "return=representation",
}


def delete_where(table: str, where: dict) -> int:
    """Delete rows from *table* matching *where* and return count."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        r = requests.delete(url, headers=HEADERS, params=where, timeout=30)
        if r.status_code not in (200, 204):
            print(f"❌ {table} delete failed {r.status_code}: {r.text[:200]}")
            return 0
        try:
            data = r.json() if r.text else []
            return len(data) if isinstance(data, list) else 0
        except Exception:
            # fall back to Content-Range count if available
            content_range = r.headers.get("Content-Range")
            if content_range and "/" in content_range:
                return int(content_range.split("/")[-1])
            return 0
    except Exception as exc:
        print(f"❌ {table} delete error: {exc}")
        return 0


def fetch_expired_market_ids(now: str) -> list[str]:
    """Return a list of market IDs with expiration < ``now``."""
    url = f"{SUPABASE_URL}/rest/v1/markets"
    params = {"expiration": f"lt.{now}", "select": "market_id"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            print(f"❌ markets fetch failed {r.status_code}: {r.text[:200]}")
            return []
        data = r.json() if r.text else []
        return [row.get("market_id") for row in data if "market_id" in row]
    except Exception as exc:
        print(f"❌ markets fetch error: {exc}")
        return []


def delete_old_snapshots(cutoff: str) -> None:
    count = delete_where("market_snapshots", {"timestamp": f"lt.{cutoff}"})
    print(f"📉 deleted {count} old snapshots (< {cutoff})")


def delete_expired_markets(now: str) -> None:
    # Remove outcomes associated with expired markets first
    expired_ids = fetch_expired_market_ids(now)
    count_o = 0
    if expired_ids:
        ids = ",".join(expired_ids)
        count_o = delete_where("market_outcomes", {"market_id": f"in.({ids})"})
    print(f"🗑️  deleted {count_o} expired outcomes")

    # Then remove expired snapshots
    count_s = delete_where("market_snapshots", {"expiration": f"lt.{now}"})
    print(f"🗑️  deleted {count_s} expired snapshots")

    # Finally remove the markets themselves
    count_m = delete_where("markets", {"expiration": f"lt.{now}"})
    print(f"🗑️  deleted {count_m} expired markets")


def delete_inactive_markets() -> None:
    # remove markets marked as resolved or cancelled
    count = delete_where("markets", {"status": "in.(RESOLVED,CANCELLED)"})
    print(f"🗑️  deleted {count} inactive markets")


def delete_low_volume_markets(threshold: int = 10) -> None:
    # Supabase REST API does not currently support querying views in DELETE
    # statements, so removing low-volume markets is left as a placeholder.
    print(
        "⚠️  low-volume market cleanup not implemented via REST API"
    )


def main(cutoff: str, *, low_volume: bool = False) -> None:
    print("== Cleanup starting ==")
    delete_old_snapshots(cutoff)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    delete_expired_markets(now)
    delete_inactive_markets()
    if low_volume:
        delete_low_volume_markets()
    print("== Cleanup done ==")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up Supabase markets")
    parser.add_argument("cutoff", nargs="?", help="cutoff timestamp for snapshots")
    parser.add_argument(
        "--low-volume",
        action="store_true",
        help="delete low-volume markets (requires DELETE_LOW_VOLUME=1)",
        default=os.getenv("DELETE_LOW_VOLUME") == "1",
    )
    args = parser.parse_args()

    cutoff = args.cutoff or os.getenv("SNAPSHOT_CUTOFF")
    if not cutoff:
        print("Provide cutoff timestamp or set SNAPSHOT_CUTOFF")
        sys.exit(1)

    main(cutoff, low_volume=args.low_volume)
