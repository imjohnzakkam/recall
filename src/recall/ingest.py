"""Ingest a single failed command into Supermemory Local.

Called fire-and-forget by the r() wrapper (via the ``recall-ingest`` console script):

    recall-ingest <command> <cwd> <exit_code> <errfile>

Renders the failure as a *described problem* (so the embeddings capture meaning, not a
raw log dump), scrubs secrets, and POSTs to /v3/documents. Also stashes the scrubbed
error to ~/.recall/last_error.txt so a bare ``recall`` (no args) has something to search.

This must never block or crash the shell: all network/errors are swallowed.
"""
import hashlib
import subprocess
import sys
import time

from . import client, config, constants, redact, render, state
from .log import get_logger

log = get_logger(__name__)


def git_ref(cwd: str) -> str:
    """Return the short HEAD ref for ``cwd``, or "" if not a repo / git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=2,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def ingest_failure(
    command: str, cwd: str, exit_code: int, err_text: str, ref: str, session: str,
) -> dict:
    """Render, post, and return the API response for one failed command."""
    err = redact.scrub(err_text)[-constants.MAX_ERROR_CHARS:]
    content = render.failure_content(
        command=command, cwd=cwd, exit_code=exit_code, err_text=err,
    )
    cid = "cmd_" + hashlib.sha1(
        f"{session}{time.time()}{command}".encode()
    ).hexdigest()[:16]
    return client.post_document(
        content,
        metadata={
            "kind": "failure",
            "command": command[:constants.MAX_COMMAND_CHARS],
            "exit_code": int(exit_code),
            "cwd": cwd,
            "git_ref": ref or "",
            "session": str(session),
            "ts": int(time.time()),
        },
        custom_id=cid,
    )


def ingest_resolution(
    error_sig: str, fix_commands: list[str], cwd: str, ref: str, session: str = "",
) -> dict:
    """Render and post a problem -> fix resolution document."""
    content = render.resolution_content(error_sig, fix_commands, cwd=cwd)
    return client.post_document(
        content,
        metadata={
            "kind": "resolution",
            "cwd": cwd,
            "git_ref": ref or "",
            "session": str(session or config.SESSION),
            "ts": int(time.time()),
            # scalar-only metadata: join for `recall --run` to execute later
            "fix_commands": constants.FIX_CMD_DELIM.join(fix_commands),
        },
    )


def _stash_last_error(scrubbed: str) -> None:
    """Best-effort write of the scrubbed error for a bare ``recall``."""
    try:
        config.RECALL_DIR.mkdir(parents=True, exist_ok=True)
        config.LAST_ERROR.write_text(scrubbed)
    except OSError as e:
        log.warning("could not stash last_error: %s", e)


def process_event(
    command: str, cwd: str, exit_code: int, err_text: str, ref: str, session: str = "",
) -> None:
    """Handle one captured command: stash + ingest a failure, and link resolutions.

    Shared by the `r`-wrapper (recall-ingest) and the ambient daemon. Never raises —
    the capture path must not break the shell.
    """
    session = session or config.SESSION
    scrubbed = redact.scrub(err_text)[-constants.MAX_ERROR_CHARS:]
    is_failure = exit_code != 0 and err_text.strip()

    # stash the last error only on a real failure, so a bare `recall` right after a
    # fix passes still points at the failure, not an empty success.
    if is_failure:
        _stash_last_error(scrubbed)

    try:
        if is_failure:
            resp = ingest_failure(command, cwd, exit_code, err_text, ref, session)
            log.info(
                "ingested failure: exit=%s cwd=%s command=%r -> id=%s",
                exit_code, cwd, command[:120], resp.get("id", "?"),
            )
        else:
            log.info("skipped ingest: exit=%s cwd=%s (success or empty output)", exit_code, cwd)
    except Exception as e:
        # never let capture break the shell
        log.warning("ingest failed for command=%r: %s", command[:120], e)

    # resolution linking: runs on every command (success and failure)
    try:
        linked = state.record(command, cwd, exit_code, scrubbed, ref)
        if linked:
            error_sig, fixes, link_ref = linked
            resp = ingest_resolution(error_sig, fixes, cwd, link_ref, session)
            log.info(
                "linked resolution: %d fix cmd(s) cwd=%s error=%r -> id=%s",
                len(fixes), cwd, error_sig[:80], resp.get("id", "?"),
            )
    except Exception as e:
        log.warning("resolution linking failed for command=%r: %s", command[:120], e)


def main() -> None:
    """Entry point for the `r` wrapper: recall-ingest <command> <cwd> <exit_code> <errfile>."""
    if len(sys.argv) < 5:
        return
    command, cwd, exit_code, errfile = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    err_text = ""
    try:
        with open(errfile, "r", errors="replace") as f:
            err_text = f.read()
    except OSError as e:
        log.warning("could not read errfile %s: %s", errfile, e)

    try:
        ec = int(exit_code)
    except ValueError:
        ec = 1

    process_event(command, cwd, ec, err_text, git_ref(cwd), config.SESSION)


if __name__ == "__main__":
    main()
