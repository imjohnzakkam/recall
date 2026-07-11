"""Setup diagnostics tests."""
from pathlib import Path
from types import SimpleNamespace

import requests

from recall import cli, config, daemon


class Response:
    ok = True
    status_code = 200

    def json(self):
        return {"models": [{"name": "qwen3:8b"}]}


def test_doctor_checks_auth_model_shell_daemon_and_storage(monkeypatch, tmp_path, capsys):
    recall_dir = tmp_path / ".recall"
    shell_dir = recall_dir / "shell"
    shell_dir.mkdir(parents=True)
    (shell_dir / "init.zsh").write_text("# recall")
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(f"source {shell_dir / 'init.zsh'}\n")

    monkeypatch.setattr(config, "RECALL_DIR", recall_dir)
    monkeypatch.setattr(config, "KEY", "sm_test")
    monkeypatch.setattr(daemon, "daemon_status", lambda: (True, 42))
    monkeypatch.setattr(Path, "expanduser", lambda self: zshrc if str(self) == "~/.zshrc" else self)
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())

    assert cli.doctor() == 0
    output = capsys.readouterr().out
    for name in ("local storage", "shell integration", "daemon", "Supermemory auth", "Ollama model"):
        assert f"✓ {name}" in output


def test_doctor_rejects_unconfigured_key(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RECALL_DIR", tmp_path / "missing")
    monkeypatch.setattr(config, "KEY", "")
    monkeypatch.setattr(daemon, "daemon_status", lambda: (False, None))
    monkeypatch.setattr(
        requests, "get",
        lambda *args, **kwargs: SimpleNamespace(ok=False, json=lambda: {"models": []}),
    )
    assert cli.doctor() == 1
