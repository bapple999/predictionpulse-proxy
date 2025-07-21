"""Lightweight ISO datetime parser for tests."""
from datetime import datetime

def isoparse(value: str) -> datetime:
    """Parse an ISO-8601 string."""
    return parse(value)

def parse(value: str) -> datetime:
    """Parse a subset of ISO-8601 strings."""
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    value = value.replace('T', ' ')
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
