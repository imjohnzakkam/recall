"""Thin wrapper over the Supermemory Local REST API.

One place that knows how to talk to ``localhost:6767`` — ingest, CLI, seed, and the
smoketest all go through here so headers, endpoints, and timeouts are defined once.
"""
from typing import Any, Optional

import requests

from . import config, constants
from .log import get_logger

log = get_logger(__name__)


def post_document(
    content: str,
    metadata: dict[str, Any],
    custom_id: Optional[str] = None,
    entity_context: Optional[str] = None,
    dreaming: str = constants.DREAMING_MODE,
) -> dict[str, Any]:
    """POST a document to /v3/documents and return the decoded JSON response."""
    body: dict[str, Any] = {
        "content": content,
        "containerTag": config.TAG,
        "dreaming": dreaming,
        "metadata": metadata,
    }
    if custom_id:
        body["customId"] = custom_id
    if entity_context:
        body["entityContext"] = entity_context

    r = requests.post(
        f"{config.BASE}{constants.DOCUMENTS_PATH}",
        headers=config.headers(),
        json=body,
        timeout=constants.HTTP_TIMEOUT,
    )
    if not r.ok:
        log.error("POST %s -> %s: %s", constants.DOCUMENTS_PATH, r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json()


def search(
    query: str,
    *,
    threshold: float = constants.DEFAULT_THRESHOLD,
    limit: int = constants.DEFAULT_LIMIT,
    rerank: bool = constants.DEFAULT_RERANK,
    exclude_session: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Hybrid semantic search via /v4/search; returns the results list (possibly empty)."""
    body: dict[str, Any] = {
        "q": query,
        "containerTag": config.TAG,
        "searchMode": constants.SEARCH_MODE,
        "rerank": rerank,          # off on Local — the reranker needs Cloudflare Workers AI
        "threshold": threshold,
        "limit": limit,
    }
    if exclude_session:
        # Hide the current shell's own *failures* (don't echo the error you're staring
        # at), but always surface resolutions — including fixes you just made this session.
        body["filters"] = {"OR": [
            {"key": "kind", "value": "resolution"},
            {"key": "session", "value": exclude_session, "negate": True},
        ]}

    r = requests.post(
        f"{config.BASE}{constants.SEARCH_PATH}",
        headers=config.headers(),
        json=body,
        timeout=constants.HTTP_TIMEOUT,
    )
    if not r.ok:
        log.error("POST %s -> %s: %s", constants.SEARCH_PATH, r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json().get("results", [])


def profile(q: Optional[str] = None) -> dict[str, Any]:
    """Fetch the auto-built container profile via /v4/profile (optional query rider)."""
    body: dict[str, Any] = {"containerTag": config.TAG}
    if q:
        body["q"] = q

    r = requests.post(
        f"{config.BASE}{constants.PROFILE_PATH}",
        headers=config.headers(),
        json=body,
        timeout=constants.HTTP_TIMEOUT,
    )
    if not r.ok:
        log.error("POST %s -> %s: %s", constants.PROFILE_PATH, r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json()
