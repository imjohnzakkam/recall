"""Distribution resource tests."""
import tempfile
from importlib.resources import files
from pathlib import Path

from recall import installer


def test_shell_resources_are_packaged():
    root = files("recall.resources")
    assert root.joinpath("init.zsh").is_file()
    assert root.joinpath("ambient.zsh").is_file()


def test_checkout_shell_files_match_packaged_resources():
    repo = Path(__file__).parents[1]
    resources = files("recall.resources")
    for name in ("init.zsh", "ambient.zsh"):
        assert (repo / "shell" / name).read_text() == resources.joinpath(name).read_text()


def test_packaged_init_starts_daemon():
    text = files("recall.resources").joinpath("init.zsh").read_text()
    assert '"$RECALL_BIN/recall" daemon start' in text
    assert "umask 077" in files("recall.resources").joinpath("ambient.zsh").read_text()


def test_installer_writes_shell_and_private_env():
    root = Path(tempfile.mkdtemp()) / "shell"
    init = installer.install(root)
    assert init.exists()
    assert (root / "ambient.zsh").exists()
    assert oct((root.parent / "env").stat().st_mode & 0o777) == "0o600"
