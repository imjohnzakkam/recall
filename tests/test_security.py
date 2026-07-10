"""Safety and whole-event redaction tests."""
from recall import redact, security


def test_redacts_commands_and_credentials():
    text = "deploy --token ghp_abcdefghijklmnopqrstuvwxyz0123 PASSWORD=hunter2secret"
    clean = redact.scrub(text)
    assert "ghp_" not in clean
    assert "hunter2secret" not in clean


def test_classifies_command_risk():
    assert security.classify("pytest -q") == security.Risk.SAFE
    assert security.classify("pip install requests") == security.Risk.CAUTION
    assert security.classify("sudo rm -rf /tmp/example") == security.Risk.DESTRUCTIVE


def test_destructive_approval_requires_run():
    command = "docker system prune -af"
    assert not security.approve(command, lambda _: "y")
    assert security.approve(command, lambda _: "RUN")


if __name__ == "__main__":
    for name, fn in sorted(globals().copy().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
