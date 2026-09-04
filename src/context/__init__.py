"""Context intelligence package.

Minimal, deterministic context selection for LLM calls (Task 3-7 of the
Context Intelligence & Token Efficiency mission).

This package is deliberately **additive and backward-compatible**. It does
not build the deferred Project Memory or the planned registries (deferred by
the refactor plan); it only adds the *selection* layer that decides which
documentation/source files a given task actually needs.

Layering (SYSTEM_RULES.md §B): this is deterministic infrastructure, so it
lives under the ``context`` namespace and depends only on ``src.core``.
"""

from __future__ import annotations

from src.context.priority import ContextPriority, Priority
from src.context.classifier import TaskCategory, classify_task
from src.context.budget import ContextBudget, DEFAULT_BUDGETS

__all__ = [
    "TaskCategory",
    "classify_task",
    "ContextPriority",
    "Priority",
    "ContextBudget",
    "DEFAULT_BUDGETS",
]
