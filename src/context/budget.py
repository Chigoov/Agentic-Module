"""Configurable context budgets (Task 6).

A context budget is the maximum number of tokens the system will feed to the
model for a given task category. These are **defaults, not absolute truths**:
a caller may raise a budget when a task genuinely requires it (e.g. an
architecture audit needs the full spec set).

The budget is enforced by the :class:`ContextLoader` / manifest pipeline:
when the selected context exceeds the budget, lower-priority documents are
dropped first (see :mod:`src.context.priority`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.context.classifier import TaskCategory

__all__ = ["ContextBudget", "DEFAULT_BUDGETS", "budget_for"]


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """A single task category's context budget.

    Attributes
    ----------
    category:
        The task category this budget applies to.
    max_context_tokens:
        Maximum total context tokens for the category.
    overrides:
        Per-document token overrides (e.g. a large doc that must always be
        counted at its real size, or a doc that may be truncated). Unused
        entries fall back to the document's measured size.
    """

    category: TaskCategory
    max_context_tokens: int
    overrides: dict[str, int] = field(default_factory=dict)


#: Default budgets per task category (tokens). Values are deliberate defaults,
#: not measured truths — see the Context Efficiency Audit for the reasoning.
DEFAULT_BUDGETS: dict[TaskCategory, int] = {
    TaskCategory.FILE_OPERATION: 4_000,
    TaskCategory.SIMPLE_CODE: 12_000,
    TaskCategory.DEBUGGING: 24_000,
    TaskCategory.TESTING: 16_000,
    TaskCategory.DOCUMENTATION: 12_000,
    TaskCategory.ARCHITECTURE: 80_000,
    TaskCategory.RESEARCH: 120_000,
    TaskCategory.VERIFICATION: 30_000,
    TaskCategory.EVIDENCE: 40_000,
    TaskCategory.WRITING: 40_000,
    TaskCategory.AUDIT: 80_000,
    TaskCategory.UNKNOWN: 24_000,
}


def budget_for(category: TaskCategory, budgets: dict[TaskCategory, int] | None = None) -> int:
    """Return the budget for ``category``, using defaults when not supplied.

    Parameters
    ----------
    category:
        The task category to look up.
    budgets:
        Optional explicit mapping; missing categories fall back to the
        default budget table.
    """
    source = budgets or DEFAULT_BUDGETS
    if category in source:
        return source[category]
    # Missing category falls back to that category's default when known,
    # else to the UNKNOWN default.
    return DEFAULT_BUDGETS.get(category, DEFAULT_BUDGETS[TaskCategory.UNKNOWN])
