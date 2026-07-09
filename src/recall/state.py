"""Failure -> success resolution linking.

The differentiator: recall remembers *fixes*, not just failures. This module tracks,
per working directory, the last failing command and the commands run since it. When a
later success re-runs the same (normalized) command in that directory, the commands in
between are the candidate fix, and we surface them as a resolution.

State is a small JSON file per cwd under ~/.recall/state/. It is best-effort and
last-writer-wins: good enough for interactive use, and it never raises so it can't break
the shell-facing capture path.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from . import config, constants
from .log import get_logger

log = get_logger(__name__)

STATE_DIR = config.RECALL_DIR / "state"

# A resolution to ingest: (error signature, fix commands, git ref of the failure).
Resolution = tuple[str, list[str], str]


def _state_path(cwd: str) -> Path:
    key = hashlib.sha1(cwd.encode()).hexdigest()[:16]
    return STATE_DIR / f"{key}.json"


def normalize(command: str) -> str:
    """Reduce a command to a comparable signature.

    Basenames the program and masks digits/hashes so a re-run matches its earlier
    failure (e.g. ``/usr/bin/docker compose up`` ~ ``docker compose up``).
    """
    toks = command.strip().split()
    if not toks:
        return ""
    toks[0] = os.path.basename(toks[0])
    norm = " ".join(toks).lower()
    norm = re.sub(r"[0-9a-f]{7,}", "#", norm)   # commit hashes, container ids
    norm = re.sub(r"\d+", "#", norm)            # ports, counts, versions
    return norm


def _load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _save(path: Path, data: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError as e:
        log.warning("could not write state %s: %s", path, e)


def _clear(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def record(
    command: str, cwd: str, exit_code: int, error_sig: str, git_ref: str = "",
) -> Optional[Resolution]:
    """Update per-cwd state; return a Resolution when a fix has just been linked.

    - Non-zero exit opens (or replaces) the tracked failure for this cwd.
    - A success that re-runs the same normalized command closes it: everything run in
      between is the fix. A success of a *different* command is remembered as a
      candidate fix step. Failures older than ``STALE_SECONDS`` are dropped.
    """
    path = _state_path(cwd)

    if exit_code != 0:
        # a new (or repeated) failure opens/replaces the tracked one
        if error_sig.strip():
            _save(path, {
                "failed_command": command,
                "error_sig": error_sig[-constants.ERROR_SIG_CHARS:],
                "git_ref": git_ref,
                "ts": int(time.time()),
                "fix_candidates": [],
            })
        return None

    # exit_code == 0 — a success
    st = _load(path)
    if not st:
        return None
    if int(time.time()) - st.get("ts", 0) > constants.STALE_SECONDS:
        _clear(path)
        return None

    if normalize(command) == normalize(st.get("failed_command", "")):
        # the failing command now passes → everything since is the fix
        fixes = st.get("fix_candidates", [])
        _clear(path)
        if fixes:
            return st["error_sig"], fixes, st.get("git_ref", "")
        return None

    # a different successful command — remember it as a candidate fix step
    fixes = st.get("fix_candidates", [])
    fixes.append(command)
    st["fix_candidates"] = fixes[-constants.MAX_FIX_CANDIDATES:]
    _save(path, st)
    return None
