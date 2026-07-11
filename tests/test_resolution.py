#!/usr/bin/env python3
"""Unit tests for the failure -> success resolution linking logic.

Pure logic, no server: exercises recall.state.record through realistic sequences.
Run directly (``python tests/test_resolution.py``) or under pytest.
"""
import os
import tempfile
from pathlib import Path

# config reads RECALL_* at import time; provide harmless defaults for a logic-only test.
os.environ.setdefault("RECALL_BASE", "http://localhost:6767")
os.environ.setdefault("RECALL_TAG", "recall_test")
os.environ.setdefault("RECALL_KEY", "sm_test")

from recall import state  # noqa: E402


def _fresh_state_dir() -> None:
    state.STATE_DIR = Path(tempfile.mkdtemp(prefix="recall_state_"))


def test_normalize_matches_reruns():
    assert state.normalize("/usr/bin/docker compose up") == state.normalize("docker compose up")
    assert state.normalize("git checkout abc1234f") == state.normalize("git checkout deadbeef")
    assert state.normalize("psql -p 5432") == state.normalize("psql -p 6789")
    assert state.normalize("pytest") != state.normalize("npm test")


def test_links_fix_on_rerun_success():
    _fresh_state_dir()
    cwd = "/work/app"
    assert state.record("docker compose up", cwd, 1, "port 8080 already allocated") is None
    # an intermediate successful fix step is remembered, not yet linked
    assert state.record("lsof -ti :8080 | xargs kill -9", cwd, 0, "") is None
    # re-running the failed command successfully closes the loop
    linked = state.record("docker compose up", cwd, 0, "")
    assert linked is not None
    error_sig, fixes, _ref, verify_command = linked
    assert "8080" in error_sig
    assert fixes == ["lsof -ti :8080 | xargs kill -9"]
    assert verify_command == "docker compose up"


def test_no_link_without_candidates():
    _fresh_state_dir()
    cwd = "/work/api"
    state.record("pytest", cwd, 1, "AssertionError")
    # immediate flaky re-run pass, nothing done in between → no meaningful fix
    assert state.record("pytest", cwd, 0, "") is None


def test_success_without_open_failure():
    _fresh_state_dir()
    assert state.record("ls", "/tmp", 0, "") is None


def test_stale_failure_dropped():
    _fresh_state_dir()
    cwd = "/work/old"
    state.record("make", cwd, 1, "boom")
    # backdate the tracked failure beyond the stale window
    path = state._state_path(cwd)
    data = state._load(path)
    data["ts"] -= state.constants.STALE_SECONDS + 10
    state._save(path, data)
    assert state.record("make", cwd, 0, "") is None


def test_new_failure_replaces_open_one():
    _fresh_state_dir()
    cwd = "/work/x"
    state.record("cmd-a", cwd, 1, "error A")
    state.record("cmd-b", cwd, 1, "error B")   # replaces the open failure
    state.record("apply-fix", cwd, 0, "")      # candidate for the current (B) failure
    linked = state.record("cmd-b", cwd, 0, "")
    assert linked is not None
    error_sig, fixes, _ref, verify_command = linked
    assert error_sig == "error B"              # paired with B, not the replaced A
    assert fixes == ["apply-fix"]
    assert verify_command == "cmd-b"


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n=== PASS === {len(tests)} resolution-linking tests")


if __name__ == "__main__":
    main()
