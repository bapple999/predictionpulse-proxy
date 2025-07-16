import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

import common

def test_chunked_basic():
    result = list(common._chunked([1, 2, 3, 4], size=2))
    assert result == [[1, 2], [3, 4]]


def test_chunked_remainder():
    result = list(common._chunked([1, 2, 3, 4, 5], size=2))
    assert result == [[1, 2], [3, 4], [5]]

def test_fetch_stats_concurrent_success():
    def fn(x):
        return x * 2
    stats, failed = common.fetch_stats_concurrent([1, 2, 3], fn)
    assert dict(stats) == {1: 2, 2: 4, 3: 6}
    assert failed == []


def test_fetch_stats_concurrent_failure():
    def fn(x):
        raise ValueError("boom")
    stats, failed = common.fetch_stats_concurrent([7], fn)
    assert stats == []
    assert failed == [7]


def test_fetch_events(monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=15):
        calls.append((url, params))

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"events": [{"id": 1}, {"id": 2}]}

        return FakeResp()

    monkeypatch.setattr(common.requests, "get", fake_get)
    events = common.fetch_events(limit=2, max_pages=1)
    assert events == [{"id": 1}, {"id": 2}]
    assert calls[0][0] == common.EVENTS_URL
