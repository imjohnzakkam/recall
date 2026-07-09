"""Centralized logging so every module logs the same readable way.

Runtime logs go to ``~/.recall/logs/recall.log`` (under ``config.LOG_DIR``, outside the
repo so they are never committed). A rotating handler keeps them bounded. Configuration
never raises: if the log directory can't be created, we fall back to a null handler so a
logging problem can never break the caller — critically, the shell-facing ``r()`` wrapper.
"""
import logging
from logging.handlers import RotatingFileHandler

from . import config

_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def get_logger(name: str) -> logging.Logger:
    """Return a module logger writing readable, rotated records to ~/.recall/logs."""
    logger = logging.getLogger(name)
    if logger.handlers:          # idempotent — configure once per process
        return logger
    logger.setLevel(logging.INFO)
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            config.LOG_DIR / "recall.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
        )
        handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
        logger.addHandler(handler)
    except OSError:              # logging must never break the caller
        logger.addHandler(logging.NullHandler())
    return logger
