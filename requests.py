"""Minimal stub of the requests module for offline testing."""

class RequestException(Exception):
    pass

class Response:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}")
    def json(self):
        return self._json

def get(url, headers=None, params=None, timeout=10):
    raise RequestException("Network access disabled")

def post(url, headers=None, json=None, timeout=30):
    raise RequestException("Network access disabled")
