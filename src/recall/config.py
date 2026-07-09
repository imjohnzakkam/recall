"""Runtime configuration, resolved once from the environment.

Reading `RECALL_*` at import time is intentional (and matches the original scripts):
a missing key fails loudly and early rather than mid-request. `init.zsh` sources
`~/.recall/env` before any entry point runs, so these are always present in normal use.
"""
import os
from pathlib import Path

BASE = os.environ["RECALL_BASE"]
TAG = os.environ["RECALL_TAG"]
HEADERS = {"Authorization": f"Bearer {os.environ['RECALL_KEY']}"}
SESSION = os.environ.get("RECALL_SESSION", "")

RECALL_DIR = Path("~/.recall").expanduser()
LAST_ERROR = RECALL_DIR / "last_error.txt"
LOG_DIR = RECALL_DIR / "logs"
