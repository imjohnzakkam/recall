"""recall — semantic recall over your terminal history.

Two modes:
    recall              act on the last captured failure
    recall "free text"  search by meaning
    recall me           what your terminal knows about how you work

Every call is to localhost — kill Wi-Fi and it still works.
"""
import sys
from typing import Any

from . import client, config
from .log import get_logger

log = get_logger(__name__)


def last_error_text() -> str:
    """Return the most recent scrubbed failure captured for a bare ``recall``."""
    return config.LAST_ERROR.read_text() if config.LAST_ERROR.exists() else ""


def render(results: list[dict[str, Any]]) -> None:
    """Print search results, surfacing resolutions (the actual fixes) first."""
    if not results:
        print("recall: no prior memory of anything like this.")
        return
    results = sorted(
        results,
        key=lambda r: (r.get("metadata") or {}).get("kind") != "resolution",
    )
    for res in results:
        body = res.get("memory") or res.get("chunk") or ""
        sim = res.get("similarity", 0.0)
        when = (res.get("updatedAt") or "")[:10]
        kind = (res.get("metadata") or {}).get("kind")
        tag = "🔧 FIX" if kind == "resolution" else "•"
        print(f"\n{tag}  [{sim:.2f}]  {when}\n{body}")


def me() -> None:
    """Print the auto-built profile of how you work (`recall me`)."""
    p = client.profile().get("profile", {})
    print("── your terminal, as recall sees it ──")
    for label, items in (("Recurring", p.get("static", [])),
                         ("Lately", p.get("dynamic", []))):
        for it in items:
            print(f"  {label:9} {it}")


def main() -> None:
    if sys.argv[1:2] == ["me"]:
        me()
        return
    query = " ".join(sys.argv[1:]) or last_error_text()
    if not query.strip():
        sys.exit("recall: nothing to recall (no recent failure, no query given).")
    results = client.search(query, exclude_session=config.SESSION or None)
    log.info("search: query=%r -> %d result(s)", query[:120], len(results))
    render(results)


if __name__ == "__main__":
    main()
