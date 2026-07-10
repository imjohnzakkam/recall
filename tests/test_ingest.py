"""Capture hardening tests without a running Supermemory server."""
import tempfile
from pathlib import Path

from recall import config, ingest


def _temp_recall_dir():
    root = Path(tempfile.mkdtemp())
    config.RECALL_DIR = root
    config.LAST_ERROR = root / "last_error.txt"
    ingest._DEDUPE_FILE = root / "recent-event.json"
    return root


def test_duplicate_window():
    _temp_recall_dir()
    assert not ingest._duplicate("pytest", "/work", 1, "boom")
    assert ingest._duplicate("r pytest", "/work", 1, "boom")


def test_empty_stderr_failure_is_ingested():
    _temp_recall_dir()
    calls = []
    old_ingest, old_record = ingest.ingest_failure, ingest.state.record
    ingest.ingest_failure = lambda *args: calls.append(args) or {"id": "x"}
    ingest.state.record = lambda *args: None
    try:
        ingest.process_event("false", "/work", 1, "", "", "s")
        assert calls
        assert "non-zero" in config.LAST_ERROR.read_text()
    finally:
        ingest.ingest_failure, ingest.state.record = old_ingest, old_record


if __name__ == "__main__":
    for name, fn in sorted(globals().copy().items()):
        if name.startswith("test_"):
            fn(); print(f"ok  {name}")
