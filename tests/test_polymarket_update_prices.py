import polymarket_update_prices as pup
from datetime import datetime, timezone, timedelta


def test_load_active_market_info_filters(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {
            "market_id": "1",
            "event_ticker": "slug1",
            "expiration": (now + timedelta(days=1)).isoformat(),
            "status": "TRADING",
        },
        {
            "market_id": "2",
            "event_ticker": "slug2",
            "expiration": (now - timedelta(days=1)).isoformat(),
            "status": "TRADING",
        },
        {
            "market_id": "3",
            "event_ticker": "slug3",
            "expiration": None,
            "status": "RESOLVED",
        },
        {
            "market_id": "4",
            "event_ticker": "slug4",
            "expiration": None,
            "status": "TRADING",
        },
    ]

    def fake_request_json(url, headers=None):
        return rows

    monkeypatch.setattr(pup, "request_json", fake_request_json)
    info = pup.load_active_market_info()
    assert set(info.keys()) == {"1", "4"}
