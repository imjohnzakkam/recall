"""Dependency-light tests for TUI presentation helpers."""
from recall import recipes, tui


def test_detail_includes_risk_context_and_evidence():
    recipe = recipes.Recipe(
        id="fix_1", problem="missing package", steps=["pip install requests"],
        cwd="/work", successes=2, failures=1,
    )
    text = tui.detail_text(recipe)
    assert "[caution]" in text
    assert "Learned in: /work" in text
    assert "2 success / 1 failure" in text
