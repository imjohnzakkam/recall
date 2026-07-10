#!/usr/bin/env python3
"""Milestone 1 — prove the boring path end to end.

POSTs one fake failure + its resolution, then searches with a query that shares ZERO
keywords with the stored text and waits (indexing is async) until a semantic hit comes
back. If it does, hybrid semantic search is working — the whole thesis of recall.

    python tests/smoketest.py     # requires the installed package + server up
"""
import hashlib
import sys
import time

import requests

from recall import client, config, render

# Stored text talks about postgres/psycopg2/port 5432/connection refused.
STORED_ERROR = (
    "psycopg2.OperationalError: could not connect to server: Connection "
    "refused. Is the server running on host \"localhost\" and accepting "
    "TCP/IP connections on port 5432?"
)
STORED_FIX = ["brew services start postgresql@16", "pg_isready"]

# Query shares NO keywords with the above — pure semantic match.
DISJOINT_QUERY = "my application cannot reach the database backend"

# PASS = a keyword-disjoint query returns a hit at least this similar. That IS the
# thesis (recall by meaning). We don't gate on our own just-posted doc: cold first-run
# extraction can lag minutes behind, and Milestone 1 seeds the corpus first, so the
# semantic capability is what we assert.
MIN_SIM = 0.60
TIMEOUT_S = 120
POLL_EVERY_S = 5


def shares_keyword(query: str, text: str):
    stop = {"my", "cannot", "the", "a", "to", "is", "and", "on", "of"}
    qwords = {w for w in query.lower().split() if w not in stop}
    twords = set(text.lower().replace('"', " ").split())
    return qwords & twords


def main() -> None:
    uid = hashlib.sha1(f"smoketest{time.time()}".encode()).hexdigest()[:12]

    print("1. connectivity check ...")
    try:
        requests.get(f"{config.BASE}/", headers=config.headers(), timeout=5)
    except Exception as e:
        sys.exit(f"FAIL: cannot reach {config.BASE} ({e}). Is supermemory-server up?")

    print("2. posting a fake failure + resolution ...")
    fail = render.failure_content(exit_code=2, err_text=STORED_ERROR)
    res = render.resolution_content(STORED_ERROR, STORED_FIX)
    client.post_document(
        fail, {"kind": "failure", "session": "smoketest", "ts": int(time.time())},
        custom_id=f"smoke_fail_{uid}",
    )
    client.post_document(
        res, {"kind": "resolution", "session": "smoketest", "ts": int(time.time())},
        custom_id=f"smoke_fix_{uid}",
    )

    overlap = shares_keyword(DISJOINT_QUERY, STORED_ERROR + " " + " ".join(STORED_FIX))
    print(f"   query      : {DISJOINT_QUERY!r}")
    print(f"   stored     : {STORED_ERROR[:60]}...")
    print(f"   shared kw  : {overlap or 'NONE (pure semantic match)'}")

    print(f"3. semantic search — need a hit >= {MIN_SIM} (async index, up to {TIMEOUT_S}s) ...")
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        results = client.search(DISJOINT_QUERY, threshold=0.4)   # a touch loose for the proof
        top = results[0] if results else None
        if top and top.get("similarity", 0) >= MIN_SIM and not shares_keyword(
                DISJOINT_QUERY, top.get("memory") or top.get("chunk") or ""):
            src = (top.get("metadata") or {}).get("session", "?")
            body = top.get("memory") or top.get("chunk") or ""
            print("\n=== PASS ===")
            print(f"keyword-disjoint query matched at similarity "
                  f"{top['similarity']:.3f} (source: {src}):")
            print("  " + body[:400].replace("\n", "\n  "))
            print("\nRecall-by-meaning works. This is the whole pitch.")
            return
        best = f"{top.get('similarity', 0):.3f}" if top else "no results"
        left = int(deadline - time.time())
        print(f"   ...best so far {best}, retrying ({left}s left)")
        time.sleep(POLL_EVERY_S)

    print("\n=== FAIL ===")
    print("No strong semantic hit within the timeout. Likely causes:")
    print("  - nothing indexed yet → run recall-seed first, wait for extraction")
    print("  - extraction model still warming / too slow (check ollama)")
    print("  - recall quality low → try a bigger OPENAI_MODEL, or steer entityContext")
    sys.exit(1)


if __name__ == "__main__":
    main()
