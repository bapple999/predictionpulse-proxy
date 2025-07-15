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
