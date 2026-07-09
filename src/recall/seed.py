"""Bootstrap the memory space for recall.

1. Sets ``entityContext`` on the container tag so the extractor knows it's looking at
   terminal command events (steers extraction quality).
2. Seeds a corpus of realistic failure + resolution pairs so the demo is never empty
   and the semantic match is guaranteed to hit.

Run once after the server is up, via the console script:
    recall-seed
"""
import hashlib
import time

from . import client, constants, render
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
    # --- databases ---
    ("psycopg2.OperationalError: could not connect to server: Connection refused. "
     "Is the server running on host \"localhost\" and accepting TCP/IP connections on port 5432?",
     ["brew services start postgresql@16", "pg_isready"], "~/work/api"),
    ("redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379. Connection refused.",
     ["brew services start redis", "redis-cli ping"], "~/work/api"),
    ("pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused",
     ["brew services start mongodb-community", "mongosh --eval 'db.runCommand({ping:1})'"], "~/work/api"),
    ("django.db.utils.OperationalError: FATAL: role \"app\" does not exist",
     ["createuser -s app", "createdb -O app appdb"], "~/work/api"),
    ("sqlalchemy.exc.OperationalError: (psycopg2) FATAL: database \"appdb\" does not exist",
     ["createdb appdb", "alembic upgrade head"], "~/work/api"),

    # --- python ---
    ("ModuleNotFoundError: No module named 'requests'",
     ["source .venv/bin/activate", "pip install requests"], "~/work/scripts"),
    ("error: externally-managed-environment. This environment is externally managed. "
     "pip install was blocked by PEP 668.",
     ["python -m venv .venv", "source .venv/bin/activate", "pip install -r requirements.txt"], "~/work/scripts"),
    ("ImportError: cannot import name 'soft_unicode' from 'markupsafe'",
     ["pip install 'markupsafe==2.0.1'"], "~/work/api"),
    ("pytest: error: unrecognized arguments: --cov. ModuleNotFoundError: No module named 'pytest_cov'",
     ["pip install pytest-cov"], "~/work/api"),
    ("zsh: command not found: python. python: command not found",
     ["brew install python@3.12", "ln -s $(brew --prefix)/bin/python3 /usr/local/bin/python"], "~/work"),

    # --- node / js ---
    ("npm ERR! code ERESOLVE unable to resolve dependency tree. Conflicting peer dependency for react@18.",
     ["rm -rf node_modules package-lock.json", "npm install --legacy-peer-deps"], "~/work/web"),
    ("Error: Cannot find module 'express'. Require stack: - /app/server.js",
     ["npm install express"], "~/work/web"),
    ("Error: listen EADDRINUSE: address already in use :::3000",
     ["lsof -ti :3000 | xargs kill -9", "npm run dev"], "~/work/web"),
    ("gyp ERR! stack Error: `xcodebuild` requires Xcode. node-gyp rebuild failed.",
     ["xcode-select --install"], "~/work/web"),
    ("npm ERR! code ETARGET. No matching version found for lodash@^99.0.0.",
     ["npm install lodash@latest"], "~/work/web"),

    # --- git ---
    ("fatal: Authentication failed for 'https://github.com/acme/app.git'. "
     "remote: Support for password authentication was removed.",
     ["gh auth login", "git remote set-url origin git@github.com:acme/app.git"], "~/work/app"),
    ("git@github.com: Permission denied (publickey). fatal: Could not read from remote repository.",
     ["ssh-add ~/.ssh/id_ed25519", "ssh -T git@github.com"], "~/work/app"),
    ("fatal: not a git repository (or any of the parent directories): .git",
     ["git init", "git remote add origin git@github.com:acme/app.git"], "~/work/new"),
    ("error: failed to push some refs. Updates were rejected because the remote contains work you do not have.",
     ["git pull --rebase origin main", "git push"], "~/work/app"),
    ("remote: error: File big.bin is 143 MB; this exceeds GitHub's file size limit of 100 MB.",
     ["git rm --cached big.bin", "git lfs track '*.bin'", "git add .gitattributes big.bin"], "~/work/app"),

    # --- docker ---
    ("Error response from daemon: driver failed programming external connectivity: "
     "Bind for 0.0.0.0:8080 failed: port is already allocated.",
     ["lsof -ti :8080 | xargs kill -9", "docker compose up -d"], "~/work/app"),
    ("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
     ["open -a Docker", "docker info"], "~/work/app"),
    ("docker: no space left on device. failed to register layer.",
     ["docker system prune -af --volumes"], "~/work/app"),
    ("WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8).",
     ["docker build --platform linux/arm64 -t app ."], "~/work/app"),

    # --- system / shell ---
    ("zsh: permission denied: ./deploy.sh",
     ["chmod +x deploy.sh", "./deploy.sh"], "~/work/app"),
    ("OSError: [Errno 24] Too many open files",
     ["ulimit -n 4096"], "~/work/api"),
    ("ssl.SSLCertVerificationError: certificate verify failed: unable to get local issuer certificate",
     ["pip install --upgrade certifi", "/Applications/Python*/Install\\ Certificates.command"], "~/work/scripts"),
    ("make: *** No rule to make target 'build'. make: command not found",
     ["xcode-select --install"], "~/work/app"),

    # --- cloud / infra ---
    ("Unable to connect to the server: dial tcp 127.0.0.1:6443: connect: connection refused (kubectl)",
     ["kubectl config use-context docker-desktop", "kubectl cluster-info"], "~/work/infra"),
    ("Error acquiring the state lock. Lock Info: ID xx... terraform state is locked.",
     ["terraform force-unlock -force $LOCK_ID"], "~/work/infra"),
    ("botocore.exceptions.NoCredentialsError: Unable to locate credentials",
     ["aws configure", "aws sts get-caller-identity"], "~/work/infra"),
    ("go: cannot find module providing package github.com/acme/app/pkg: working directory is not part of a module",
     ["go mod init github.com/acme/app", "go mod tidy"], "~/work/go-svc"),
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
            metadata={
                "kind": "resolution", "cwd": cwd, "ts": int(time.time()), "session": "seed",
                "fix_commands": constants.FIX_CMD_DELIM.join(fixes),
            },
            custom_id=f"seedfix_{sig}",
        )
        print(f"seeded pair {i + 1}/{len(PAIRS)}")


def main() -> None:
    set_entity_context()
    seed_pairs()
    log.info("seeded %d failure/resolution pairs", len(PAIRS))
    print(f"\nSeeded {len(PAIRS)} pairs. Indexing is async — give it ~1-2 min before searching.")


if __name__ == "__main__":
    main()
