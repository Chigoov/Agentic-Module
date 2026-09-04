"""Context manifest (Task 5).

Before a model call, the system records *what* context was selected and *why*.
The manifest is JSON-serializable for auditability: it reports which files
were included, which were skipped, the reasoning, and an estimated token size.

A manifest is produced AFTER selection and budget trimming, so it reflects the
final, actually-used context — not the pre-budget wish-list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.context.classifier import TaskCategory
from src.context.priority import Priority

__all__ = ["ContextManifest", "ManifestEntry"]


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """A single document's selection record.

    Attributes
    ----------
    name:
        Stable key / relative path of the document (not necessarily a file).
    priority:
        The load priority used for the decision.
    selected:
        Whether this document was included in the final context.
    tokens:
        Estimated token size (0 when skipped).
    reason:
        Why this was included or excluded.
    """

    name: str
    priority: Priority
    selected: bool
    tokens: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority.name,
            "selected": self.selected,
            "tokens": self.tokens,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ContextManifest:
    """Auditability record for a single context-selection event.

    Attributes
    ----------
    task_id:
        Caller-supplied identifier for the task.
    task_type:
        The classified task category.
    task_target:
        Optional hint about the specific file/module/area targeted.
    entries:
        Per-document selection records, in selection order.
    estimated_context_tokens:
        Total estimated tokens of `selected` entries.
    budget_tokens:
        The enforced budget (0 when no budget applied).
    over_budget:
        Whether the pre-budget selection exceeded ``budget_tokens`` (i.e.
        trimming occurred).
    """

    task_id: str
    task_type: TaskCategory
    task_target: str | None = None
    entries: list[ManifestEntry] = field(default_factory=list)
    estimated_context_tokens: int = 0
    budget_tokens: int = 0
    over_budget: bool = False

    @property
    def files_selected(self) -> list[str]:
        return [entry.name for entry in self.entries if entry.selected]

    @property
    def files_skipped(self) -> list[str]:
        return [entry.name for entry in self.entries if not entry.selected]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "task_target": self.task_target,
            "files_selected": self.files_selected,
            "files_skipped": self.files_skipped,
            "entries": [entry.to_dict() for entry in self.entries],
            "estimated_context_size": self.estimated_context_tokens,
            "budget_tokens": self.budget_tokens,
            "over_budget": self.over_budget,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Render the manifest as pretty JSON (for logs / audit artifacts)."""
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
