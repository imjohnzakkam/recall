"""The recall terminal theme — hand-rolled ANSI 256-color styling, no dependencies.

Colors are emitted only to an interactive TTY, and suppressed when output is piped
or ``NO_COLOR`` is set, so recall stays scriptable. ``FORCE_COLOR`` overrides for demos.
"""
import os
import sys
import time

_RESET = "\033[0m"

# 256-color palette — the recall theme
_PALETTE = {
    "fix": 78,       # emerald — a remembered fix
    "bullet": 245,   # grey — a plain failure memory
    "cmd": 44,       # teal — shell commands
    "head": 141,     # violet — headers / brand accent
    "label": 110,    # slate blue — field labels
    "warn": 173,     # muted orange
    "muted": 244,    # dim grey — problem text, match/time trailer
}


def _enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


_ON = _enabled()


def paint(text: str, color: str, bold: bool = False) -> str:
    """Wrap text in the palette color, or return it unchanged when color is off."""
    if not _ON:
        return text
    code = _PALETTE.get(color, 7)
    weight = "1;" if bold else ""
    return f"\033[{weight}38;5;{code}m{text}{_RESET}"


def ago(ts: int) -> str:
    """Human relative time from a unix timestamp: 'just now', '2h ago', '3d ago'."""
    if not ts:
        return ""
    delta = int(time.time()) - int(ts)
    if delta < 60:
        return "just now"
    # (upper bound in seconds, seconds-per-unit, suffix)
    for limit, secs, suffix in (
        (3600, 60, "m"),          # < 1h  -> minutes
        (86400, 3600, "h"),       # < 1d  -> hours
        (604800, 86400, "d"),     # < 1w  -> days
        (2592000, 604800, "w"),   # < 30d -> weeks
        (31536000, 2592000, "mo"),  # < 1y  -> months
    ):
        if delta < limit:
            return f"{delta // secs}{suffix} ago"
    return f"{delta // 31536000}y ago"


def header(text: str) -> str:
    return paint(text, "head", bold=True)


def command(text: str) -> str:
    return paint(text, "cmd")


def label(text: str) -> str:
    return paint(text, "label")


def warn(text: str) -> str:
    return paint(text, "warn")


def dim(text: str) -> str:
    return paint(text, "muted")
