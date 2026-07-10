"""recall — semantic recall over your terminal history.

Modes:
    recall               act on the last captured failure
    recall "free text"   search by meaning
    recall --run [text]  apply the top remembered fix (after y/N)
    recall me            what your terminal knows about how you work

Every call is to localhost — kill Wi-Fi and it still works.
"""
import os
import re
import subprocess
import sys
from typing import Any

from . import client, config, constants, security, theme
from .log import get_logger

log = get_logger(__name__)


def last_error_text() -> str:
    """Return the most recent scrubbed failure captured for a bare ``recall``."""
    return config.LAST_ERROR.read_text() if config.LAST_ERROR.exists() else ""


def _sorted_fixes_first(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda r: (r.get("metadata") or {}).get("kind") != "resolution",
    )


MAX_RESULTS = 5
_NOISE_MARKERS = ("executed in the directory", "working directory for", "the command was run")


def render(results: list[dict[str, Any]]) -> None:
    """Print search results as a fix-first list, deduped and de-noised.

    Resolutions lead with the fix command(s); the problem and match/time are dimmed
    beneath. Plain failures (no known fix) show as a single dim line. Identical fixes
    are collapsed and low-signal directory-only memories are dropped.
    """
    seen: set = set()
    shown = 0
    for res in _sorted_fixes_first(results):
        kind = (res.get("metadata") or {}).get("kind")
        if kind == "resolution":
            fixes = _fix_commands(res)
            if not fixes:
                continue
            key = ("fix", tuple(fixes))
            if key in seen:
                continue
            seen.add(key)
            _render_resolution(res, fixes)
        else:
            body = _clean(res)
            if _low_signal(body):
                continue
            key = ("mem", body)
            if key in seen:
                continue
            seen.add(key)
            _render_memory(body, res)
        shown += 1
        if shown >= MAX_RESULTS:
            break
    if shown == 0:
        print(theme.dim("recall: no prior memory of anything like this."))


def _meta(res: dict[str, Any]) -> str:
    """Dim '0.92 · 2h ago' trailer from similarity + ingest timestamp."""
    sim = res.get("similarity", 0.0)
    ts = (res.get("metadata") or {}).get("ts")
    when = theme.ago(ts) if ts else (res.get("updatedAt") or "")[:10]
    trailer = f"{sim:.2f} · {when}" if when else f"{sim:.2f}"
    return theme.dim(trailer)


def _render_resolution(res: dict[str, Any], fixes: list[str]) -> None:
    """Fix command(s) as the hero line(s); problem + match/time dimmed beneath."""
    print()
    for cmd in fixes:
        print(theme.paint(cmd, "cmd", bold=True))
    print(f"  {theme.dim('↳')} {_problem_text(res)}   {_meta(res)}")


def _render_memory(body: str, res: dict[str, Any]) -> None:
    """A plain failure with no known fix: one dim line so it recedes behind fixes."""
    print()
    print(f"{theme.dim(body)}   {_meta(res)}")


def _clean(res: dict[str, Any]) -> str:
    return " ".join((res.get("memory") or res.get("chunk") or "").split())


def _low_signal(text: str) -> bool:
    """True for content-free memories (directory-only facts the extractor sometimes emits)."""
    t = text.lower()
    if not t:
        return True
    if t.startswith("directory:"):
        return True
    return any(marker in t for marker in _NOISE_MARKERS)


def _problem_text(res: dict[str, Any]) -> str:
    """Pull the problem description out of a resolution body (best-effort)."""
    body = res.get("memory") or res.get("chunk") or ""
    m = re.search(r"Problem:\s*(.*?)\s*(?:Directory:|Fix\b|$)", body, re.S)
    text = m.group(1) if m and m.group(1).strip() else re.split(r"Fix\b", body, 1)[0]
    return " ".join(text.replace("RESOLUTION.", "").split()) or "(unknown)"


def _fix_commands(res: dict[str, Any]) -> list[str]:
    """Extract runnable fix commands from a resolution result.

    Prefers the scalar ``fix_commands`` metadata written at ingest; falls back to
    splitting ``$ cmd`` occurrences out of the document body (handles inline text
    where the stored newlines were collapsed).
    """
    raw = (res.get("metadata") or {}).get("fix_commands")
    if raw:
        return [c.strip() for c in raw.split(constants.FIX_CMD_DELIM) if c.strip()]
    body = res.get("chunk") or res.get("memory") or ""
    segment = re.split(r"pass:\s*", body, 1)[-1]
    return [c.strip() for c in re.split(r"\s*\$\s+", segment) if c.strip()]


def run_top_fix(query: str) -> None:
    """Find the best remembered fix for ``query`` and, after confirmation, run it."""
    resolutions = [
        r for r in client.search(query, exclude_session=config.SESSION or None)
        if (r.get("metadata") or {}).get("kind") == "resolution"
    ]
    if not resolutions:
        print(theme.warn("recall --run: no remembered fix for this. Try `recall` to look."))
        return

    top = _sorted_fixes_first(resolutions)[0]
    commands = _fix_commands(top)
    if not commands:
        print(theme.warn("recall --run: found a fix but couldn't extract runnable commands:"))
        render([top])
        return

    print(theme.header("recall would run this remembered fix:"))
    for c in commands:
        print("  " + theme.command(f"$ {c}") + theme.dim(f"  [{security.label(c)}]"))

    for c in commands:
        if not security.approve(c):
            print(theme.dim("aborted."))
            return
        print(theme.dim(f"\n$ {c}"))
        rc = subprocess.run(c, shell=True).returncode
        if rc != 0:
            print(theme.warn(f"stopped: `{c}` exited {rc}."))
            return
    print(theme.paint("✓ done — the remembered fix ran clean.", "fix", bold=True))


def init_config() -> None:
    config.RECALL_DIR.mkdir(parents=True, exist_ok=True)
    env = config.RECALL_DIR / "env"
    if not env.exists():
        env.write_text(
            'export RECALL_BASE="http://localhost:6767"\n'
            f'export RECALL_TAG="{config.TAG}"\n'
            'export RECALL_KEY="sm_..."\n'
        )
        os.chmod(env, 0o600)
    print(f"recall: configuration ready at {env}")
    print("Edit RECALL_KEY, then source the shell integration described in `recall doctor`.")


def doctor() -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("config directory", os.access(config.RECALL_DIR, os.W_OK), str(config.RECALL_DIR)))
    checks.append(("RECALL_KEY", bool(config.KEY and config.KEY != "sm_..."), "run `recall init`, then edit ~/.recall/env"))
    from . import daemon
    running, pid = daemon.daemon_status()
    checks.append(("daemon", running, f"pid {pid}" if pid else "run `recall daemon start`"))
    try:
        r = __import__("requests").get(config.BASE, timeout=2)
        checks.append(("Supermemory", r.status_code < 500, config.BASE))
    except Exception as exc:
        checks.append(("Supermemory", False, str(exc)))
    try:
        r = __import__("requests").get("http://localhost:11434/api/tags", timeout=2)
        checks.append(("Ollama", r.ok, "http://localhost:11434"))
    except Exception as exc:
        checks.append(("Ollama", False, str(exc)))
    for name, ok, detail in checks:
        print(f"{'✓' if ok else '✗'} {name}: {detail}")
    return 0 if all(c[1] for c in checks) else 1


def daemon_command(action: str) -> None:
    from . import daemon
    if action == "start":
        print(f"recall daemon started (pid {daemon.start_daemon()})")
    elif action == "stop":
        print("recall daemon stopped" if daemon.stop_daemon() else "recall daemon is not running")
    elif action == "status":
        running, pid = daemon.daemon_status()
        print(f"recall daemon: {'running (pid ' + str(pid) + ')' if running else 'stopped'}")
    else:
        raise SystemExit("usage: recall daemon start|stop|status")


def usage() -> None:
    print(__doc__.strip())
    print("\nSetup: recall init | recall doctor | recall daemon start|stop|status")


def me() -> None:
    """Print the auto-built profile of how you work (`recall me`)."""
    p = client.profile().get("profile", {})
    print(theme.header("── your terminal, as recall sees it ──"))
    for name, items in (("Recurring", p.get("static", [])),
                        ("Lately", p.get("dynamic", []))):
        for it in items:
            print(f"  {theme.label(f'{name:9}')} {it}")


def main() -> None:
    raw = sys.argv[1:]
    if not raw or raw[0] not in {"--help", "-h", "init", "doctor", "daemon"}:
        pass
    elif raw[0] in {"--help", "-h"}:
        usage(); return
    elif raw[0] == "init":
        init_config(); return
    elif raw[0] == "doctor":
        raise SystemExit(doctor())
    elif raw[0] == "daemon":
        daemon_command(raw[1] if len(raw) > 1 else "status"); return

    args = [a for a in sys.argv[1:] if a != "--run"]
    do_run = "--run" in sys.argv[1:]

    if args[:1] == ["me"]:
        me()
        return

    query = " ".join(args) or last_error_text()
    if not query.strip():
        sys.exit("recall: nothing to recall (no recent failure, no query given).")

    if do_run:
        run_top_fix(query)
        return

    try:
        results = client.search(query, exclude_session=config.SESSION or None)
    except Exception as exc:
        raise SystemExit(f"recall: {exc}")
    log.info("search: query=%r -> %d result(s)", query[:120], len(results))
    render(results)


if __name__ == "__main__":
    main()
