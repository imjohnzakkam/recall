"""Runtime configuration with setup-safe defaults and explicit validation."""
import os
import socket
from pathlib import Path

# Keep configuration importable before setup so ``recall --help``, ``init`` and
# ``doctor`` can explain what is missing instead of crashing with KeyError.
BASE = os.environ.get("RECALL_BASE", "http://localhost:6767").rstrip("/")
TAG = os.environ.get("RECALL_TAG", f"recall_{socket.gethostname().split('.')[0]}")
KEY = os.environ.get("RECALL_KEY", "")
SESSION = os.environ.get("RECALL_SESSION", "")

RECALL_DIR = Path("~/.recall").expanduser()
LAST_ERROR = RECALL_DIR / "last_error.txt"
LOG_DIR = RECALL_DIR / "logs"
PID_FILE = RECALL_DIR / "daemon.pid"


class ConfigError(RuntimeError):
    """An actionable configuration error suitable for terminal display."""


def headers() -> dict[str, str]:
    if not KEY or KEY == "sm_...":
        raise ConfigError("RECALL_KEY is not configured; run `recall init` or edit ~/.recall/env.")
    return {"Authorization": f"Bearer {KEY}"}
