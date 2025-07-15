from datetime import datetime, timezone
from dateutil.parser import parse

# replicate timezone handling from polymarket_fetch

def normalize_dt(exp_raw):
    exp_dt = parse(exp_raw)
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    else:
        exp_dt = exp_dt.astimezone(timezone.utc)
    return exp_dt


def test_expiration_comparison_naive():
    now = datetime.now(timezone.utc)
    exp_dt = normalize_dt("2020-01-01 00:00:00")
    assert exp_dt <= now

