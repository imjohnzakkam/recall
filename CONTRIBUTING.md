# Contributing

Use Python 3.10+ and zsh on macOS for the supported capture path.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,tui]'
pytest -q
ruff check .
```

Keep shell capture non-blocking, redact before persistence or network calls, and add tests
for behavior changes. Use focused branches and explain user impact and verification in pull
requests. Never commit `.supermemory`, `~/.recall`, API keys, or captured terminal output.
