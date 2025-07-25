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

from kalshi_fetch import format_market_row


def test_format_market_row_basic():
    event = {"title": "Presidential Election", "ticker": "EVT"}
    market = {
        "ticker": "EVT-BIDEN",
        "close_time": "2024-11-05T00:00:00Z",
    }
    row = format_market_row(event, market)
    assert row["market_id"] == "EVT-BIDEN"
    assert row["market_name"] == "BIDEN"
    assert row["event_ticker"] == "EVT"
    assert row["market_description"] == "Presidential Election"
    assert row["status"] == "TRADING"
    assert row["tags"] == ["kalshi"]


def test_format_market_row_event_ticker_fallback():
    event = {"title": "New Pope", "event_ticker": "EVT-POPE"}
    market = {
        "ticker": "EVT-POPE-JOHN",
        "close_time": "2030-01-01T00:00:00Z",
    }
    row = format_market_row(event, market)
    assert row["market_id"] == "EVT-POPE-JOHN"
    assert row["market_name"] == "JOHN"
    assert row["event_ticker"] == "EVT-POPE"
    assert row["market_description"] == "New Pope"
