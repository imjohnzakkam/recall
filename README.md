# recall

**Your terminal remembers how you fixed it.**

`recall` captures failed commands, searches previous incidents by meaning, and returns the
commands that made the problem go away. Supermemory Local and Ollama keep capture,
extraction, embeddings, and search on your machine.

```text
$ pytest -q
ModuleNotFoundError: No module named 'pytest_cov'

$ recall
pip install pytest-cov
  ↳ pytest did not recognize --cov · worked 3 times
```

## Why recall

- Semantic search finds related failures even when their wording differs.
- Failure-to-success linking learns fixes from normal work.
- Secret redaction runs before ingestion.
- Plain CLI output remains pipe-friendly and respects `NO_COLOR`.
- Local-first operation keeps high-volume terminal data private.

## Install

Prerequisites: macOS, zsh, Python 3.10+, [Ollama](https://ollama.com), and
[Supermemory Local](https://github.com/supermemoryai/supermemory).

```bash
ollama pull qwen3:8b
pipx install supermemory-recall       # or: uv tool install supermemory-recall
recall-init
# edit ~/.recall/env and set the sm_... key printed by Supermemory Local
echo 'source ~/.recall/shell/init.zsh' >> ~/.zshrc
exec zsh
```

From a checkout, use `python -m pip install -e '.[dev,tui]'`.

## Use

```bash
pytest -q                         # failures are captured ambiently
recall                            # search using the last captured failure
recall "database unavailable"     # search by meaning
recall --run                      # preview and confirm the top remembered fix
recall me                         # summarize recurring terminal patterns
r pytest -q                       # explicitly capture one command
```

Ambient capture mirrors stderr only, leaving stdout attached to its TTY. Disable it with
`export RECALL_AMBIENT=0`. Runtime data lives under `~/.recall/`.

## How it works

```text
zsh hooks → capture daemon → redact/render → Supermemory Local
    ↑                                      ↓ hybrid search
    └────────────── recall CLI ← problem + remembered fix
```

When a command fails and a later equivalent command succeeds in the same directory,
intervening successful commands become a candidate resolution. See
[Architecture](docs/architecture.md) and [Security](docs/security.md).

## Troubleshooting and removal

See [Troubleshooting](docs/troubleshooting.md). To disable capture, remove the `source`
line from `.zshrc`. To remove local Recall state, stop its daemon and delete `~/.recall`.
Deleting Supermemory documents is separate because that database owns indexed memories.

## Project

Built for the Supermemory Local Hackathon. See the [hackathon brief](docs/hackathon.md)
and [contribution guide](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
