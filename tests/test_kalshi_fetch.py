import pytest


def test_sort_none_dollar_volume():
    markets = [
        {"ticker": "A", "dollar_volume_24h": None},
        {"ticker": "B", "dollar_volume_24h": 100},
        {"ticker": "C"},
        {"ticker": "D", "dollar_volume_24h": 50},
    ]
    kept = sorted(markets, key=lambda m: m.get("dollar_volume_24h") or 0, reverse=True)
    assert [m["ticker"] for m in kept] == ["B", "D", "A", "C"]
