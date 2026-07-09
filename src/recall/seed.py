"""Bootstrap the memory space for recall.

1. Sets ``entityContext`` on the container tag so the extractor knows it's looking at
   terminal command events (steers extraction quality).
2. Seeds a small corpus of realistic failure + resolution pairs so the demo is never
   empty. (The full 30-50-pair corpus is a Day-5 task.)

Run once after the server is up, via the console script:
    recall-seed
"""
import hashlib
import time

from . import client, render
from .log import get_logger

log = get_logger(__name__)

ENTITY_CONTEXT = (
    "These documents are terminal command events. Each has a command, "
    "an exit code, a working directory, and (on failure) an error message. "
    "Some documents are RESOLUTIONS: they pair an error signature with the "
    "commands that fixed it. Extract the error's meaning and the fix steps."
)

# (error signature, [fix commands], directory hint)
PAIRS = [
    (
        "psycopg2.OperationalError: could not connect to server: Connection "
        "refused. Is the server running on host \"localhost\" and accepting "
        "TCP/IP connections on port 5432?",
        ["brew services start postgresql@16", "pg_isready"],
        "~/work/api",
    ),
    (
        "error: externally-managed-environment. This environment is externally "
        "managed. pip install was blocked by PEP 668.",
        ["python -m venv .venv", "source .venv/bin/activate", "pip install -r requirements.txt"],
        "~/work/scripts",
    ),
    (
        "fatal: Authentication failed for 'https://github.com/acme/app.git'. "
        "remote: Support for password authentication was removed.",
        ["gh auth login", "git remote set-url origin git@github.com:acme/app.git"],
        "~/work/app",
    ),
    (
        "Error response from daemon: driver failed programming external "
        "connectivity: Bind for 0.0.0.0:8080 failed: port is already allocated.",
        ["lsof -ti :8080 | xargs kill -9", "docker compose up -d"],
        "~/work/app",
    ),
    (
        "npm ERR! code ERESOLVE unable to resolve dependency tree. Conflicting "
        "peer dependency for react@18.",
        ["rm -rf node_modules package-lock.json", "npm install --legacy-peer-deps"],
        "~/work/web",
    ),
]


def set_entity_context() -> None:
    """Persist the extraction-steering entityContext on the container tag."""
    resp = client.post_document(
        "Terminal session bootstrap for recall.",
        metadata={"kind": "bootstrap"},
        entity_context=ENTITY_CONTEXT,
    )
    print(f"entityContext set on container: {resp.get('id', '?')}")


def seed_pairs() -> None:
    """Post each demo failure and its paired resolution document."""
    for i, (err, fixes, cwd) in enumerate(PAIRS):
        sig = hashlib.sha1(err.encode()).hexdigest()[:12]
        client.post_document(
            render.failure_content(cwd=cwd, err_text=err),
            metadata={"kind": "failure", "cwd": cwd, "ts": int(time.time()), "session": "seed"},
            custom_id=f"seedfail_{sig}",
        )
        client.post_document(
            render.resolution_content(err, fixes, cwd=cwd),
            metadata={"kind": "resolution", "cwd": cwd, "ts": int(time.time()), "session": "seed"},
            custom_id=f"seedfix_{sig}",
        )
        print(f"seeded pair {i + 1}/{len(PAIRS)}")


def main() -> None:
    set_entity_context()
    seed_pairs()
    log.info("seeded %d failure/resolution pairs", len(PAIRS))
    print("\nSeeded. Indexing is async — give it ~30–60s before searching.")


if __name__ == "__main__":
    main()
