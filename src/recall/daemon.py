"""Ambient capture daemon — the "always on, no `r` needed" path.

One long-running process watches every interactive shell's control file
(``~/.recall/session.<S>.ctl``, written by shell/ambient.zsh) and, for each command
that finishes, slices that command's stderr out of the matching ``session.<S>.log`` by
byte offset and hands it to ``ingest.process_event`` — the same pipeline the `r` wrapper
uses. Failures become memories; a fix that makes an earlier failure pass becomes a
resolution. Documents are tagged with the *originating* shell session (parsed from the
filename) so the CLI's session filter still works.

Run it via the console script (started automatically by init.zsh):
    recall-daemon
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import config, ingest
from .log import get_logger

log = get_logger(__name__)

POLL_SECONDS = 1.0
TAIL_LINES = 40          # keep the last N lines of a failed command's stderr
SESSION_RETENTION_SECONDS = 7 * 24 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 60


def daemon_status() -> tuple[bool, int | None]:
    try:
        pid = int(config.PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True, pid
    except (OSError, ValueError):
        return False, None


def start_daemon() -> int:
    running, pid = daemon_status()
    if running and pid:
        return pid
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(config.LOG_DIR / "daemon.out.log", "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "recall.daemon"], stdout=log_file, stderr=log_file,
        start_new_session=True,
    )
    return proc.pid


def stop_daemon() -> bool:
    running, pid = daemon_status()
    if not running or not pid:
        config.PID_FILE.unlink(missing_ok=True)
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def _claim_pid() -> bool:
    config.RECALL_DIR.mkdir(parents=True, exist_ok=True)
    running, _ = daemon_status()
    if running:
        return False
    config.PID_FILE.write_text(str(os.getpid()))
    return True


def _log_for(ctl: Path) -> Path:
    """session.<S>.ctl -> session.<S>.log"""
    return ctl.with_suffix(".log")


def _session_of(ctl: Path) -> str:
    """session.<S>.ctl -> <S>"""
    return ctl.stem.removeprefix("session.")


def _slice(logpath: Path, start: int, end: int) -> str:
    """Return the last TAIL_LINES of logpath[start:end] as decoded text."""
    try:
        with open(logpath, "rb") as f:
            f.seek(max(0, start))
            data = f.read(max(0, end - start))
    except OSError:
        return ""
    text = data.decode("utf-8", "replace")
    return "\n".join(text.splitlines()[-TAIL_LINES:])


def handle_line(ctl: Path, line: str, pending: dict) -> None:
    """Parse one control-file line; on EXIT, process the just-finished command."""
    parts = line.split("\t")
    if parts[0] == "CMD" and len(parts) >= 6:
        _, _ts, pwd, ref, start, cmd = parts[0], parts[1], parts[2], parts[3], parts[4], \
            "\t".join(parts[5:])
        pending[ctl] = {"pwd": pwd, "ref": ref, "start": _to_int(start), "cmd": cmd}
    elif parts[0] == "EXIT" and len(parts) >= 4:
        event = pending.pop(ctl, None)
        if not event:
            return
        ec = _to_int(parts[2])
        end = _to_int(parts[3])
        err_text = _slice(_log_for(ctl), event["start"], end) if ec != 0 else ""
        try:
            ingest.process_event(
                event["cmd"], event["pwd"], ec, err_text, event["ref"], _session_of(ctl),
            )
        except Exception as e:            # process_event already guards, belt-and-suspenders
            log.warning("process_event failed: %s", e)


def _to_int(s: str) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    if not _claim_pid():
        log.info("ambient daemon already running")
        return
    log.info("ambient daemon started, watching %s/session.*.ctl", config.RECALL_DIR)
    offsets: dict[Path, int] = {}     # ctl -> bytes already read
    pending: dict[Path, dict] = {}    # ctl -> the open CMD awaiting its EXIT
    # skip history in files that already exist: only ingest commands that happen
    # while the daemon is running, so a restart never re-ingests past sessions.
    for ctl in config.RECALL_DIR.glob("session.*.ctl"):
        try:
            offsets[ctl] = ctl.stat().st_size
        except OSError:
            pass
    last_cleanup = 0.0
    try:
        while True:
            for ctl in sorted(config.RECALL_DIR.glob("session.*.ctl")):
                _drain(ctl, offsets, pending)
            now = time.time()
            if now - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
                cleanup_sessions(offsets, pending, now=now)
                last_cleanup = now
            time.sleep(POLL_SECONDS)
    except (KeyboardInterrupt, SystemExit):
        log.info("ambient daemon stopped")
    finally:
        try:
            if config.PID_FILE.read_text().strip() == str(os.getpid()):
                config.PID_FILE.unlink()
        except OSError:
            pass


def _drain(ctl: Path, offsets: dict, pending: dict) -> None:
    """Read any new lines appended to a control file since we last looked."""
    try:
        size = ctl.stat().st_size
    except OSError:
        return
    off = offsets.get(ctl, 0)
    if size < off:            # file was truncated (new shell reused the name)
        off = 0
        pending.pop(ctl, None)
    if size == off:
        return
    try:
        with open(ctl, "r", errors="replace") as f:
            f.seek(off)
            chunk = f.read()
            offsets[ctl] = f.tell()
    except OSError:
        return
    for line in chunk.splitlines():
        if line:
            handle_line(ctl, line, pending)


def cleanup_sessions(offsets: dict, pending: dict, *, now: float | None = None) -> int:
    """Delete inactive session capture pairs older than the retention window."""
    now = time.time() if now is None else now
    removed = 0
    controls = list(config.RECALL_DIR.glob("session.*.ctl"))
    for ctl in controls:
        log_path = _log_for(ctl)
        paths = [path for path in (ctl, log_path) if path.exists()]
        if not paths:
            continue
        try:
            newest = max(path.stat().st_mtime for path in paths)
        except OSError:
            continue
        if now - newest < SESSION_RETENTION_SECONDS:
            continue
        for path in paths:
            try:
                path.unlink()
            except OSError:
                pass
        offsets.pop(ctl, None)
        pending.pop(ctl, None)
        removed += 1
    if removed:
        log.info("removed %d stale shell session capture(s)", removed)
    return removed


if __name__ == "__main__":
    main()
