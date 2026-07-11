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
    recipes.feedback(recipe.id, True)
    assert recipes.edit(recipe.id, ["new"]).steps == ["new"]
    assert recipes.get(recipe.id).successes == 0
    assert recipes.forget(recipe.id)
    assert recipes.get(recipe.id) is None


def test_observed_recipe_is_verified_and_deduplicated():
    fresh_db()
    first = recipes.create(
        "connection refused", ["start service"], verify_command="retry",
        cwd="/work", verified=True,
    )
    assert first.successes == 1
    assert first.verify_command == "retry"
    second = recipes.create(
        "connection refused", ["start service"], verify_command="retry",
        cwd="/work", verified=True,
    )
    assert second.id == first.id
    assert second.successes == 2


def test_failed_feedback_does_not_refresh_last_verified():
    fresh_db()
    recipe = recipes.create("boom", ["fix"], verified=True)
    verified_at = recipe.last_verified
    updated = recipes.feedback(recipe.id, False)
    assert updated.failures == 1
    assert updated.last_verified == verified_at


if __name__ == "__main__":
    for name, fn in sorted(globals().copy().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
