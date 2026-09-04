"""ContextLoader — minimum relevant context selection (Task 4).

Given a task category and optional task target, the loader returns the
**minimum** set of context documents required, honoring:
- priorities (Task 7): P0 mandatory is never dropped;
- budgets (Task 6): if the selection exceeds the budget, lower-priority
  documents are trimmed first;
- auditability (Task 5): every selection decision is recorded in a
  :class:`ContextManifest`.

The loader is a pure recommendation engine. It does NOT read document contents
or make LLM calls; it produces a list of document keys (names/relative paths)
that the caller may then resolve and feed to the model. Token sizes are
estimated from text length (``bytes / 4``), which is a standard approximation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from src.context.classifier import TaskCategory
from src.context.manifest import ContextManifest, ManifestEntry
from src.context.priority import ContextPriority, Priority

__all__ = ["ContextLoader", "ContextDocument"]

#: Lowest token estimate for an empty/unknown document.
_ESTIMATED_TOKEN_BYTES = 4

#: Default per-task-type relevant document sets (P0/P1/P2), keyed by category.
#: ``None`` means "no default set — the caller must supply candidates".
#: This is a minimal, honest default: critical constitution/authority files
#: are P0 for research/architecture; simple code tasks get a tiny set.
_DEFAULT_RULES: dict[TaskCategory, tuple[ContextPriority, ...]] = {
    TaskCategory.ARCHITECTURE: (
        ContextPriority("SYSTEM_INDEX.md", Priority.P0, "Navigation layer; always read first."),
        ContextPriority("ENGINEERING_PROTOCOL.md", Priority.P0, "Golden rule: architecture review first."),
        ContextPriority("ARCHITECTURE.md", Priority.P0, "Layered architecture authority."),
        ContextPriority("AGENT_CONSTITUTION.md", Priority.P1, "Immutable rules for architectural decisions."),
        ContextPriority("00_MASTER_INSTRUCTION.md", Priority.P1, "System identity and filesystem rules."),
    ),
    TaskCategory.RESEARCH: (
        ContextPriority("AGENT_CONSTITUTION.md", Priority.P0, "Academic integrity and evidence policy."),
        ContextPriority("WORKFLOW.md", Priority.P0, "Research lifecycle and state machines."),
        ContextPriority("ARCHITECTURE.md", Priority.P1, "Tool/agent layering."),
    ),
    TaskCategory.DEBUGGING: (
        ContextPriority("SYSTEM_RULES.md", Priority.P1, "Coding and verification rules."),
    ),
    TaskCategory.TESTING: (
        ContextPriority("SYSTEM_RULES.md", Priority.P1, "Testing and verification rules."),
    ),
    TaskCategory.DOCUMENTATION: (
        ContextPriority("SYSTEM_INDEX.md", Priority.P1, "Document hierarchy and singles-source-of-truth."),
        ContextPriority("ENGINEERING_PROTOCOL.md", Priority.P1, "Documentation-update policy."),
    ),
    TaskCategory.VERIFICATION: (
        ContextPriority("AGENT_CONSTITUTION.md", Priority.P0, "Evidence verification policy."),
        ContextPriority("WORKFLOW.md", Priority.P0, "Source/claim state machine."),
    ),
    TaskCategory.WRITING: (
        ContextPriority("AGENT_CONSTITUTION.md", Priority.P0, "Integrity rules for prose."),
        ContextPriority("WORKFLOW.md", Priority.P1, "Synthesis flow."),
    ),
    TaskCategory.SIMPLE_CODE: (
        ContextPriority("SYSTEM_RULES.md", Priority.P2, "Minimal engineering rules."),
        ContextPriority("ENGINEERING_PROTOCOL.md", Priority.P2, "Minimal process rules."),
    ),
    TaskCategory.AUDIT: (
        ContextPriority("ENGINEERING_PROTOCOL.md", Priority.P0, "Audit lifecycle."),
        ContextPriority("ARCHITECTURE.md", Priority.P0, "Architecture baseline."),
        ContextPriority("SYSTEM_INDEX.md", Priority.P0, "What exists vs claimed."),
    ),
    TaskCategory.FILE_OPERATION: (
        ContextPriority("SYSTEM_RULES.md", Priority.P2, "Filesystem safety rules."),
    ),
    TaskCategory.EVIDENCE: (
        ContextPriority("AGENT_CONSTITUTION.md", Priority.P0, "Evidence policy."),
        ContextPriority("WORKFLOW.md", Priority.P1, "Evidence extraction flow."),
    ),
    TaskCategory.UNKNOWN: (
        ContextPriority("SYSTEM_INDEX.md", Priority.P0, "Unclassified — load navigation first."),
    ),
}


class ContextDocument:
    """A document the loader can consider.

    Attributes
    ----------
    name:
        Stable key / path of the document (e.g. ``src.core.config`` or
        ``docs/PHASE_1_REPORT.md``).
    size_bytes:
        Approximate content size in bytes; used to estimate tokens.
    priority:
        The load priority under the current task type.
    reason:
        Why this document is relevant (for the manifest).
    """

    __slots__ = ("name", "size_bytes", "priority", "reason")

    def __init__(self, name: str, size_bytes: int, priority: Priority, reason: str) -> None:
        self.name = name
        self.size_bytes = max(0, size_bytes)
        self.priority = priority
        self.reason = reason

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens from bytes (``bytes / 4``), rounded up to >= 0."""
        return (self.size_bytes + _ESTIMATED_TOKEN_BYTES - 1) // _ESTIMATED_TOKEN_BYTES if self.size_bytes else 0

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ContextDocument(name={self.name!r}, bytes={self.size_bytes}, priority={self.priority.name})"


#: Signature used to customize per-document token estimation.
TokenEstimator = Callable[[ContextDocument], int]


class ContextLoader:
    """Selects the minimum relevant context for a task, honoring budget."""

    def __init__(
        self,
        *,
        token_estimator: TokenEstimator | None = None,
        budget: int | None = None,
        default_candidates: Sequence[ContextDocument] | None = None,
    ) -> None:
        """Configure a loader.

        Parameters
        ----------
        token_estimator:
            Optional override for token estimation; defaults to bytes/4.
        budget:
            Optional max context tokens; when ``None``, no budget is enforced.
        default_candidates:
            Optional base candidate pool; when ``None``, candidates are passed
            per-call to :meth:`select`.
        """
        self._token_estimator = token_estimator or (lambda doc: doc.estimated_tokens)
        self._budget = budget
        self._default_candidates = list(default_candidates) if default_candidates else None

    def _estimate(self, doc: ContextDocument) -> int:
        return self._token_estimator(doc)

    def select(
        self,
        *,
        task_type: TaskCategory,
        task_id: str,
        candidates: Sequence[ContextDocument] | None = None,
        task_target: str | None = None,
        budget: int | None = None,
    ) -> ContextManifest:
        """Produce the minimum context set + manifest.

        Selection order:
        1. Compose the candidate pool (per-call candidates, or the configured
           default candidates).
        2. Sort by priority (P0 first), then by size (smaller first) so that
           small mandatory docs always land first.
        3. Greedily include documents whose estimated tokens fit the budget,
           never dropping P0.
        4. Build the manifest recording selected/skipped + reasoning.
        """
        effective_budget = budget if budget is not None else self._budget
        pool = list(candidates) if candidates is not None else (self._default_candidates or [])

        # Compose an ordered candidate list preserving the caller's pool order,
        # but sort by (priority, size) for deterministic selection.
        ordered = sorted(pool, key=lambda doc: (doc.priority, doc.estimated_tokens))
        seen: set[str] = set()
        selected: list[ContextDocument] = []
        skipped: list[ManifestEntry] = []
        total = 0
        over_budget = False

        for doc in ordered:
            if doc.name in seen:
                continue
            seen.add(doc.name)
            tokens = self._estimate(doc)
            # P0 is mandatory; always include. Others must fit the budget.
            if effective_budget is not None and doc.priority is not Priority.P0 and total + tokens > effective_budget:
                over_budget = True
                skipped.append(
                    ManifestEntry(
                        name=doc.name,
                        priority=doc.priority,
                        selected=False,
                        tokens=tokens,
                        reason=f"Budget exceeded: {tokens} tokens would push total beyond {effective_budget}.",
                    )
                )
                continue
            selected.append(doc)
            total += tokens

        entries = [
            ManifestEntry(
                name=doc.name,
                priority=doc.priority,
                selected=True,
                tokens=self._estimate(doc),
                reason=doc.reason,
            )
            for doc in selected
        ] + skipped

        return ContextManifest(
            task_id=task_id,
            task_type=task_type,
            task_target=task_target,
            entries=entries,
            estimated_context_tokens=total,
            budget_tokens=effective_budget or 0,
            over_budget=over_budget,
        )

    def default_rules(self, task_type: TaskCategory) -> tuple[ContextPriority, ...]:
        """Return the default relevant-document rules for a task type."""
        return _DEFAULT_RULES.get(task_type, _DEFAULT_RULES[TaskCategory.UNKNOWN])
