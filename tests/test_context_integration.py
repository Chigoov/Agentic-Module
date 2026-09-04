"""Integration-verification tests for the context dry-run harness.

These lock in that the context selection layer is actually *executed* via the
real harness (not merely unit-tested): classification runs, candidates are
selected, P0 is never dropped, irrelevant docs are excluded, the budget is
enforced, and a manifest is produced. Purely deterministic — no network, no LLM.
"""

from __future__ import annotations

import json

from src.context.classifier import TaskCategory
from src.context.dry_run import run_dry_run, EXAMPLES
from src.context.priority import Priority


def _manifest_for(category: TaskCategory) -> object:
    """Run the real harness and return the manifest for a given example task."""
    for label, text in EXAMPLES:
        if label == category.value:
            return run_dry_run(text, task_id=f"t_{label.lower()}")
    raise AssertionError(f"No example for {category}")


def test_dry_run_executes_simple_code() -> None:
    manifest = _manifest_for(TaskCategory.SIMPLE_CODE)
    assert manifest.task_type is TaskCategory.SIMPLE_CODE
    assert manifest.files_selected  # non-empty selected set
    # P0 is never dropped.
    for entry in manifest.entries:
        if entry.priority is Priority.P0:
            assert entry.selected


def test_dry_run_executes_architecture() -> None:
    manifest = _manifest_for(TaskCategory.ARCHITECTURE)
    assert manifest.task_type is TaskCategory.ARCHITECTURE
    # ARCHITECTURE.md is P0 and must be selected.
    names = [e.name for e in manifest.entries if e.selected]
    assert "ARCHITECTURE.md" in names


def test_dry_run_executes_research() -> None:
    manifest = _manifest_for(TaskCategory.RESEARCH)
    assert manifest.task_type is TaskCategory.RESEARCH
    names = [e.name for e in manifest.entries if e.selected]
    assert "src/tools/publish_or_perish.py" in names


def test_dry_run_excludes_historical_docs() -> None:
    manifest = _manifest_for(TaskCategory.RESEARCH)
    selected_names = [e.name for e in manifest.entries if e.selected]
    # Historical docs are P4 and must never be selected.
    assert not any(n.startswith("docs/") for n in selected_names)


def test_dry_run_p0_never_dropped_even_over_budget() -> None:
    """Force a tiny budget; P0 must still be selected."""
    manifest = run_dry_run(
        "search for sources about machine learning",
        task_id="t_tiny",
        budget=10,  # absurdly small
    )
    p0_entries = [e for e in manifest.entries if e.priority is Priority.P0]
    assert p0_entries, "Expected at least one P0 doc"
    for entry in p0_entries:
        assert entry.selected, f"P0 {entry.name} must not be dropped"


def test_dry_run_budget_enforced() -> None:
    """With a small budget, non-P0 selection must not exceed the budget, and the
    manifest must flag over-budget when P0 (mandatory) pushed past it."""
    manifest = run_dry_run(
        "refactor the repository layering for modularity",
        task_id="t_budget",
        budget=2_000,
    )
    # P0 docs are mandatory and never dropped, so the total MAY exceed budget.
    assert manifest.over_budget is True
    # Budget is enforced for non-P0 documents: their sum must fit the budget.
    non_p0_selected = [e for e in manifest.entries if e.selected and e.priority is not Priority.P0]
    assert sum(e.tokens for e in non_p0_selected) <= 2_000
    # P0 docs remain selected despite overshoot.
    p0_selected = [e for e in manifest.entries if e.selected and e.priority is Priority.P0]
    assert p0_selected, "P0 docs must remain selected even when over budget"


def test_dry_run_manifest_serializable() -> None:
    manifest = _manifest_for(TaskCategory.SIMPLE_CODE)
    payload = json.loads(manifest.to_json())
    assert payload["task_type"] == "SIMPLE_CODE"
    assert "files_selected" in payload
    assert "files_skipped" in payload


def test_examples_present() -> None:
    labels = {label for label, _ in EXAMPLES}
    assert {TaskCategory.SIMPLE_CODE, TaskCategory.ARCHITECTURE, TaskCategory.RESEARCH}.issubset(labels)
