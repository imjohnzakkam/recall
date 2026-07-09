#!/usr/bin/env python3
"""Unit tests for the ambient daemon's parsing and slicing.

Pure logic, no server: verifies offset slicing and CMD/EXIT handling by stubbing
ingest.process_event. Run directly or under pytest.
"""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("RECALL_BASE", "http://localhost:6767")
os.environ.setdefault("RECALL_TAG", "recall_test")
os.environ.setdefault("RECALL_KEY", "sm_test")

from recall import daemon  # noqa: E402


def test_log_and_session_derivation():
    ctl = Path("/home/x/.recall/session.4242.ctl")
    assert daemon._log_for(ctl) == Path("/home/x/.recall/session.4242.log")
    assert daemon._session_of(ctl) == "4242"


def test_slice_returns_offset_window_tail():
    d = Path(tempfile.mkdtemp())
    logp = d / "session.1.log"
    # bytes 0..6 belong to an earlier command; the failure's stderr starts at offset 6
    logp.write_text("before\nboom line 1\nboom line 2\n")
    start = len("before\n")
    end = logp.stat().st_size
    out = daemon._slice(logp, start, end)
    assert "before" not in out
    assert out == "boom line 1\nboom line 2"


def test_handle_line_pairs_cmd_and_exit(monkeypatch=None):
    calls = []
    orig = daemon.ingest.process_event
    daemon.ingest.process_event = lambda *a: calls.append(a)
    try:
        d = Path(tempfile.mkdtemp())
        ctl = d / "session.99.ctl"
        logp = d / "session.99.log"
        logp.write_text("ModuleNotFoundError: No module named 'flask'\n")
        pending = {}
        start = 0
        end = logp.stat().st_size
        daemon.handle_line(ctl, f"CMD\t1700\t/work/api\tabc123\t{start}\tpython app.py", pending)
        assert ctl in pending
        daemon.handle_line(ctl, f"EXIT\t1701\t1\t{end}", pending)
        assert ctl not in pending           # paired and consumed
        assert len(calls) == 1
        command, cwd, ec, err_text, ref, session = calls[0]
        assert command == "python app.py"
        assert cwd == "/work/api"
        assert ec == 1
        assert "ModuleNotFoundError" in err_text
        assert session == "99"
    finally:
        daemon.ingest.process_event = orig


def test_success_exit_passes_empty_err_text():
    calls = []
    orig = daemon.ingest.process_event
    daemon.ingest.process_event = lambda *a: calls.append(a)
    try:
        d = Path(tempfile.mkdtemp())
        ctl = d / "session.7.ctl"
        (d / "session.7.log").write_text("noise\n")
        pending = {}
        daemon.handle_line(ctl, "CMD\t1\t/w\t\t0\tls", pending)
        daemon.handle_line(ctl, "EXIT\t2\t0\t6", pending)
        assert calls[0][2] == 0            # exit code
        assert calls[0][3] == ""           # no stderr sliced on success
    finally:
        daemon.ingest.process_event = orig


def test_exit_without_pending_cmd_is_ignored():
    calls = []
    orig = daemon.ingest.process_event
    daemon.ingest.process_event = lambda *a: calls.append(a)
    try:
        daemon.handle_line(Path("/x/session.5.ctl"), "EXIT\t1\t1\t10", {})
        assert calls == []
    finally:
        daemon.ingest.process_event = orig


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n=== PASS === {len(tests)} daemon tests")


if __name__ == "__main__":
    main()
