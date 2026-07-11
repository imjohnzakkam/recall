"""CLI recipe execution safety tests."""
from types import SimpleNamespace

from recall import cli


def test_execute_commands_uses_recorded_shell_and_per_command_approval(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    approvals = []
    calls = []
    monkeypatch.setattr(cli.security, "approve", lambda command: approvals.append(command) or True)
    monkeypatch.setattr(cli.shutil, "which", lambda shell: f"/bin/{shell}")
    monkeypatch.setattr(
        cli.subprocess, "run",
        lambda args: calls.append(args) or SimpleNamespace(returncode=0),
    )

    assert cli.execute_commands(["first", "second"], verify_command="check", shell="zsh")
    assert approvals == ["first", "second", "check"]
    assert calls == [
        ["/bin/zsh", "-lc", "first"],
        ["/bin/zsh", "-lc", "second"],
        ["/bin/zsh", "-lc", "check"],
    ]


def test_execute_commands_stops_on_directory_mismatch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    monkeypatch.setattr(cli.security, "approve", lambda _command: (_ for _ in ()).throw(
        AssertionError("command approval should not be reached")
    ))
    assert cli.execute_commands(["echo unsafe"], learned_cwd="/another/project") is None
