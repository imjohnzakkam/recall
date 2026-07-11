"""Supermemory HTTP request contract tests."""
import os

os.environ.setdefault("RECALL_BASE", "http://localhost:6767")
os.environ.setdefault("RECALL_TAG", "recall_test")
os.environ.setdefault("RECALL_KEY", "sm_test")

from recall import client, constants  # noqa: E402


class Response:
    ok = True
    status_code = 200
    text = ""
    def raise_for_status(self): pass
    def json(self): return {"results": [{"similarity": 0.9}]}


def test_search_request_contract(monkeypatch):
    seen = {}
    monkeypatch.setattr(client.config, "KEY", "sm_test")
    monkeypatch.setattr(client.config, "TAG", "recall_test")
    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()
    monkeypatch.setattr(client.requests, "post", post)
    assert client.search("database unavailable")
    assert seen["url"].endswith(constants.SEARCH_PATH)
    assert seen["json"]["searchMode"] == "hybrid"
    assert seen["json"]["containerTag"] == "recall_test"
