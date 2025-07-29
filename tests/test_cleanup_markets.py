import os
import sys
import types

# Provide a minimal requests placeholder so importing cleanup_markets succeeds
fake_requests = types.ModuleType("requests")
fake_requests.delete = lambda *a, **k: None
fake_requests.get = lambda *a, **k: None
sys.modules.setdefault("requests", fake_requests)

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cleanup_markets as cm


def test_delete_expired_markets_order(monkeypatch):
    calls = []

    def fake_delete_where(table, where):
        calls.append((table, where))
        return 1

    monkeypatch.setattr(cm, "delete_where", fake_delete_where)
    monkeypatch.setattr(cm, "fetch_expired_market_ids", lambda now: ["a", "b"])

    cm.delete_expired_markets("2024-01-01T00:00:00Z")

    assert calls == [
        ("market_outcomes", {"market_id": "in.(a,b)"}),
        ("market_snapshots", {"expiration": "lt.2024-01-01T00:00:00Z"}),
        ("markets", {"expiration": "lt.2024-01-01T00:00:00Z"}),
    ]
