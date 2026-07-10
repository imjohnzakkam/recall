"""Distribution resource tests."""
import tempfile
from importlib.resources import files
from pathlib import Path

from recall import installer


def test_shell_resources_are_packaged():
    root = files("recall.resources")
    assert root.joinpath("init.zsh").is_file()
    assert root.joinpath("ambient.zsh").is_file()


def test_installer_writes_shell_and_private_env():
    root = Path(tempfile.mkdtemp()) / "shell"
    init = installer.install(root)
    assert init.exists()
    assert (root / "ambient.zsh").exists()
    assert oct((root.parent / "env").stat().st_mode & 0o777) == "0o600"
