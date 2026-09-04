"""Tests for the context-intelligence layer (Tasks 3-7).

Covers task classification, context selection, priority handling, budget
enforcement, mandatory-context inclusion, optional-context exclusion, and the
auditability manifest. All tests are pure/deterministic — no external calls.
"""

from __future__ import annotations

import pytest

from src.context.budget import DEFAULT_BUDGETS, budget_for
from src.context.classifier import TaskCategory, classify_task
from src.context.loader import ContextDocument, ContextLoader
from src.context.manifest import ContextManifest
from src.context.priority import Priority


# --------------------------------------------------------------------------- #
# Task 3 — Task classification
# --------------------------------------------------------------------------- #
class TestClassification:
    def test_unknown_empty(self) -> None:
        assert classify_task("") is TaskCategory.UNKNOWN

    def test_unknown_no_keyword(self) -> None:
        assert classify_task("xyzzy plugh something vague") is TaskCategory.UNKNOWN

    def test_debugging_beat_generic_code(self) -> None:
        # "bug" must classify as DEBUGGING even though "code" also appears.
        assert classify_task("fix the bug in this code") is TaskCategory.DEBUGGING

    def test_research_discovery(self) -> None:
        assert classify_task("search for sources with crossref") is TaskCategory.RESEARCH

    def test_audit_beats_code(self) -> None:
        assert classify_task("audit the architecture and code") is TaskCategory.AUDIT

    def test_architecture_refactor(self) -> None:
        assert classify_task("refactor the layering for modularity") is TaskCategory.ARCHITECTURE

    def test_testing(self) -> None:
        assert classify_task("add unit tests for coverage") is TaskCategory.TESTING

    def test_documentation(self) -> None:
        assert classify_task("update the documentation and README") is TaskCategory.DOCUMENTATION


# --------------------------------------------------------------------------- #
# Task 7 — Priority vocabulary
# --------------------------------------------------------------------------- #
class TestPriority:
    def test_ordering(self) -> None:
        assert Priority.P0 < Priority.P1 < Priority.P2 < Priority.P3 < Priority.P4

    def test_context_priority_repr(self) -> None:
        from src.context.priority import ContextPriority

        cp = ContextPriority("X.md", Priority.P1, "reason")
        assert cp.name == "X.md"
        assert cp.priority is Priority.P1
        assert cp.reason == "reason"


# --------------------------------------------------------------------------- #
# Task 6 — Budgets
# --------------------------------------------------------------------------- #
class TestBudget:
    def test_default_budgets_present(self) -> None:
        for cat in TaskCategory:
            assert cat in DEFAULT_BUDGETS

    def test_budget_for_unknown_falls_back(self) -> None:
        # Unknown is a real category, so it returns its own default.
        assert budget_for(TaskCategory.UNKNOWN) == DEFAULT_BUDGETS[TaskCategory.UNKNOWN]

    def test_budget_for_custom(self) -> None:
        custom = {TaskCategory.SIMPLE_CODE: 5_000}
        assert budget_for(TaskCategory.SIMPLE_CODE, custom) == 5_000
        # Falling back to default when category absent.
        assert budget_for(TaskCategory.ARCHITECTURE, custom) == DEFAULT_BUDGETS[TaskCategory.ARCHITECTURE]


# --------------------------------------------------------------------------- #
# Task 4 + 5 + 6 + 7 — ContextLoader, manifest, budget, priority
# --------------------------------------------------------------------------- #
class TestContextLoader:
    def _doc(self, name: str, size_bytes: int, priority: Priority, reason: str = "rel") -> ContextDocument:
        return ContextDocument(name=name, size_bytes=size_bytes, priority=priority, reason=reason)

    def test_selects_all_within_budget(self) -> None:
        loader = ContextLoader(budget=10_000)
        docs = [
            self._doc("A.md", 100, Priority.P0),
            self._doc("B.md", 100, Priority.P1),
            self._doc("C.md", 100, Priority.P2),
        ]
        manifest = loader.select(task_type=TaskCategory.SIMPLE_CODE, task_id="t1", candidates=docs)
        assert manifest.files_selected == ["A.md", "B.md", "C.md"]
        assert manifest.estimated_context_tokens == 75  # 300 bytes / 4

    def test_p0_always_included_even_over_budget(self) -> None:
        loader = ContextLoader(budget=100)
        docs = [
            self._doc("MANDATORY.md", 10_000, Priority.P0, "must have"),
            self._doc("OPTIONAL.md", 10_000, Priority.P2),
        ]
        manifest = loader.select(task_type=TaskCategory.ARCHITECTURE, task_id="t2", candidates=docs)
        assert "MANDATORY.md" in manifest.files_selected
        assert "OPTIONAL.md" in manifest.files_skipped
        assert manifest.over_budget is True

    def test_budget_trims_lower_priority_first(self) -> None:
        loader = ContextLoader(budget=50)
        docs = [
            self._doc("P1.md", 100, Priority.P1),
            self._doc("P0.md", 10, Priority.P0),
            self._doc("P2.md", 100, Priority.P2),
        ]
        manifest = loader.select(task_type=TaskCategory.DEBUGGING, task_id="t3", candidates=docs)
        # P0 and P1 should be kept; P2 dropped; total fits within 50 tokens.
        assert "P0.md" in manifest.files_selected
        assert "P1.md" in manifest.files_selected
        assert "P2.md" in manifest.files_skipped
        assert manifest.estimated_context_tokens <= 50
        assert manifest.over_budget is True

    def test_manifest_is_serializable(self) -> None:
        loader = ContextLoader(budget=10_000)
        docs = [self._doc("A.md", 100, Priority.P0)]
        manifest = loader.select(task_type=TaskCategory.RESEARCH, task_id="t4", candidates=docs)
        data = manifest.to_dict()
        assert data["task_type"] == "RESEARCH"
        assert "files_selected" in data
        assert "files_skipped" in data
        assert data["estimated_context_size"] == 25
        # JSON round-trips.
        import json

        json_str = manifest.to_json()
        assert json.loads(json_str)["task_id"] == "t4"

    def test_default_candidates_used_when_none_passed(self) -> None:
        docs = [self._doc("Only.md", 100, Priority.P0)]
        loader = ContextLoader(default_candidates=docs)
        manifest = loader.select(task_type=TaskCategory.TESTING, task_id="t5")
        assert manifest.files_selected == ["Only.md"]

    def test_empty_pool_returns_empty_manifest(self) -> None:
        loader = ContextLoader()
        manifest = loader.select(task_type=TaskCategory.UNKNOWN, task_id="t6", candidates=[])
        assert isinstance(manifest, ContextManifest)
        assert manifest.files_selected == []
        assert manifest.estimated_context_tokens == 0

    def test_no_budget_means_no_trim(self) -> None:
        loader = ContextLoader()  # no budget
        docs = [self._doc("Big.md", 100_000, Priority.P2)]
        manifest = loader.select(task_type=TaskCategory.DOCUMENTATION, task_id="t7", candidates=docs)
        assert "Big.md" in manifest.files_selected
        assert manifest.over_budget is False
        assert manifest.budget_tokens == 0
