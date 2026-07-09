"""Render terminal events as described problems.

The content sent to Supermemory should read like a described problem so the embeddings
capture *meaning*, not a raw log dump. Both templates take optional fields so the
ingest, seed, and smoketest call sites share one implementation.
"""
from typing import Optional, Sequence


def failure_content(
    command: Optional[str] = None,
    cwd: Optional[str] = None,
    exit_code: Optional[int] = None,
    err_text: str = "",
) -> str:
    """Render a failed command as a described problem (omitting fields not provided)."""
    lines = ["A shell command failed."]
    if command is not None:
        lines.append(f"Command: {command}")
    if cwd is not None:
        lines.append(f"Directory: {cwd}")
    if exit_code is not None:
        lines.append(f"Exit code: {exit_code}")
    lines.append(f"Error output:\n{err_text}")
    return "\n".join(lines)


def resolution_content(
    error_sig: str,
    fix_commands: Sequence[str],
    cwd: Optional[str] = None,
) -> str:
    """Render a problem -> fix pairing as a RESOLUTION document."""
    lines = ["RESOLUTION.", f"Problem: {error_sig}"]
    if cwd is not None:
        lines.append(f"Directory: {cwd}")
    lines.append("Fix — these commands made it pass:")
    lines.extend(f"  $ {c}" for c in fix_commands)
    return "\n".join(lines)
