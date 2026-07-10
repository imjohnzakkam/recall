"""Safety policy for remembered shell commands.

The policy is deliberately conservative: semantic memory is untrusted input.  A
remembered command is never made safer merely because it worked in the past.
"""
import re
from enum import IntEnum


class Risk(IntEnum):
    SAFE = 0
    CAUTION = 1
    DESTRUCTIVE = 2


_DESTRUCTIVE = (
    r"(^|\s)sudo(\s|$)", r"(^|\s)rm\s+.*(?:-[a-zA-Z]*r|--recursive)",
    r"\bgit\s+(?:reset\s+--hard|clean\s+-[a-zA-Z]*f|push\s+.*--force)\b",
    r"\bdocker\s+system\s+prune\b", r"\bterraform\s+force-unlock\b",
    r"\b(?:mkfs|shutdown|reboot|killall)\b", r"\bcurl\b.*\|\s*(?:ba|z|fi)?sh\b",
    r"\bwget\b.*\|\s*(?:ba|z|fi)?sh\b", r">\s*/(?:etc|usr|bin|sbin)/",
)
_CAUTION = (
    r"(?:^|\s)rm\s", r"\bkill\s", r"\bxargs\s+kill\b", r"\bchmod\s",
    r"\bchown\s", r"\b(?:pip|npm|brew|apt|dnf)\s+(?:install|uninstall|remove)\b",
    r"\bgit\s+(?:checkout|restore|rebase|push)\b", r"[|;&><]",
    r"\$\(|`", r"\$[A-Za-z_{]",
)


def classify(command: str) -> Risk:
    text = command.strip()
    if any(re.search(p, text, re.I) for p in _DESTRUCTIVE):
        return Risk.DESTRUCTIVE
    if any(re.search(p, text, re.I) for p in _CAUTION):
        return Risk.CAUTION
    return Risk.SAFE


def label(command: str) -> str:
    return classify(command).name.lower()


def approve(command: str, input_fn=input) -> bool:
    """Request approval proportional to risk; destructive commands require typing RUN."""
    risk = classify(command)
    prompt = "Run this command? [y/N] " if risk == Risk.SAFE else \
        "This command changes system/project state. Run it? [y/N] "
    if risk == Risk.DESTRUCTIVE:
        prompt = "Destructive command detected. Type RUN to execute: "
    try:
        answer = input_fn(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == "RUN" if risk == Risk.DESTRUCTIVE else answer.lower() == "y"
