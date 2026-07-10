"""Structured recipe persistence, evidence, and ranking tests."""
import tempfile
from pathlib import Path

from recall import recipes


def fresh_db():
    recipes.DB_PATH = Path(tempfile.mkdtemp()) / "recipes.db"


def test_recipe_round_trip_and_feedback():
    fresh_db()
    recipe = recipes.create("port is occupied", ["lsof -ti :3000"], cwd="/work")
    assert recipes.get(recipe.id).steps == ["lsof -ti :3000"]
    before = recipe.confidence
    updated = recipes.feedback(recipe.id, True)
    assert updated.successes == 1
    assert updated.confidence > before
    failed = recipes.feedback(recipe.id, False)
    assert failed.failures == 1


def test_ranking_uses_query_and_context():
    fresh_db()
    wanted = recipes.create("postgres connection refused", ["brew services start postgresql"], cwd="/api")
    recipes.create("node module missing", ["npm install"], cwd="/web")
    assert recipes.ranked("database postgres unavailable", "/api")[0].id == wanted.id


def test_edit_and_forget():
    fresh_db()
    recipe = recipes.create("boom", ["old"])
    assert recipes.edit(recipe.id, ["new"]).steps == ["new"]
    assert recipes.forget(recipe.id)
    assert recipes.get(recipe.id) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().copy().items()):
        if name.startswith("test_"):
            fn(); print(f"ok  {name}")
