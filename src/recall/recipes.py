"""Local structured fix recipes and verification evidence."""
import json
import math
import os
import platform
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from . import config

DB_PATH = config.RECALL_DIR / "recipes.db"


@dataclass
class Recipe:
    id: str
    problem: str
    steps: list[str]
    verify_command: str = ""
    cwd: str = ""
    platform: str = ""
    shell: str = ""
    source: str = "observed"
    successes: int = 0
    failures: int = 0
    created_at: int = 0
    last_verified: int = 0

    @property
    def confidence(self) -> float:
        return (self.successes + 1) / (self.successes + self.failures + 2)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 3)
        return data


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS recipes (
        id TEXT PRIMARY KEY, problem TEXT NOT NULL, steps TEXT NOT NULL,
        verify_command TEXT NOT NULL, cwd TEXT NOT NULL, platform TEXT NOT NULL,
        shell TEXT NOT NULL, source TEXT NOT NULL, successes INTEGER NOT NULL,
        failures INTEGER NOT NULL, created_at INTEGER NOT NULL, last_verified INTEGER NOT NULL
    )""")
    return db


def create(
    problem: str, steps: list[str], *, verify_command: str = "", cwd: str = "",
    source: str = "observed", recipe_id: Optional[str] = None,
) -> Recipe:
    recipe = Recipe(
        id=recipe_id or "fix_" + uuid.uuid4().hex[:12], problem=problem,
        steps=list(steps), verify_command=verify_command, cwd=cwd,
        platform=platform.system().lower(), shell=Path(os.environ.get("SHELL", "")).name,
        source=source, created_at=int(time.time()),
    )
    with _connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (recipe.id, recipe.problem, json.dumps(recipe.steps), recipe.verify_command,
             recipe.cwd, recipe.platform, recipe.shell, recipe.source, recipe.successes,
             recipe.failures, recipe.created_at, recipe.last_verified),
        )
    return recipe


def get(recipe_id: str) -> Optional[Recipe]:
    with _connect() as db:
        row = db.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
    return _from_row(row) if row else None


def all_recipes() -> list[Recipe]:
    with _connect() as db:
        rows = db.execute("SELECT * FROM recipes ORDER BY last_verified DESC, created_at DESC").fetchall()
    return [_from_row(row) for row in rows]


def ranked(query: str, cwd: str = "") -> list[Recipe]:
    words = set(re.findall(r"[a-z0-9_]+", query.lower()))
    now = int(time.time())
    def score(recipe: Recipe) -> float:
        haystack = set(re.findall(r"[a-z0-9_]+", (recipe.problem + " " + " ".join(recipe.steps)).lower()))
        lexical = len(words & haystack) / max(1, len(words))
        freshness = math.exp(-max(0, now - (recipe.last_verified or recipe.created_at)) / 7_776_000)
        context = 1.0 if cwd and recipe.cwd == cwd else 0.0
        return lexical * 0.45 + recipe.confidence * 0.35 + freshness * 0.1 + context * 0.1
    return sorted(all_recipes(), key=score, reverse=True)


def feedback(recipe_id: str, worked: bool) -> Optional[Recipe]:
    now = int(time.time())
    field = "successes" if worked else "failures"
    with _connect() as db:
        db.execute(
            f"UPDATE recipes SET {field}={field}+1, last_verified=? WHERE id=?",
            (now, recipe_id),
        )
    return get(recipe_id)


def edit(recipe_id: str, steps: list[str]) -> Optional[Recipe]:
    with _connect() as db:
        db.execute("UPDATE recipes SET steps=? WHERE id=?", (json.dumps(steps), recipe_id))
    return get(recipe_id)


def forget(recipe_id: str) -> bool:
    with _connect() as db:
        cur = db.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
    return cur.rowcount > 0


def _from_row(row) -> Recipe:
    return Recipe(
        id=row[0], problem=row[1], steps=json.loads(row[2]), verify_command=row[3],
        cwd=row[4], platform=row[5], shell=row[6], source=row[7], successes=row[8],
        failures=row[9], created_at=row[10], last_verified=row[11],
    )
