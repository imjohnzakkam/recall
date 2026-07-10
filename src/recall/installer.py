"""Install packaged shell integration without relying on a source checkout."""
import os
import shutil
from importlib.resources import files
from pathlib import Path


def install(destination: Path | None = None) -> Path:
    root = destination or Path("~/.recall/shell").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    resources = files("recall.resources")
    for name in ("init.zsh", "ambient.zsh"):
        with resources.joinpath(name).open("rb") as src, (root / name).open("wb") as dst:
            shutil.copyfileobj(src, dst)
    env = root.parent / "env"
    if not env.exists():
        env.write_text(
            'export RECALL_BASE="http://localhost:6767"\n'
            'export RECALL_TAG="recall_$(hostname -s)"\n'
            'export RECALL_KEY="sm_..."\n'
        )
        os.chmod(env, 0o600)
    return root / "init.zsh"


def main() -> None:
    init = install()
    print(f"Installed recall shell integration at {init}")
    print(f"Add this to ~/.zshrc:\n  source {init}")
