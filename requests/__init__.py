class Response:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"status {self.status_code}")

def get(*args, **kwargs):
    raise NotImplementedError("requests.get is not implemented in this stub")

def post(*args, **kwargs):
    raise NotImplementedError("requests.post is not implemented in this stub")
