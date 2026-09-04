"""Context priority vocabulary (Task 7).

Every context document can be assigned a load priority. The priority drives
*both* the ContextLoader (what to include by default) and the budget enforcer
(what to drop first when over budget).

Priorities are ordered P0 (mandatory) through P4 (do not load unless
explicitly required). This is a closed, deterministic vocabulary so that the
selection logic can be reasoned about without loading any document.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["Priority", "ContextPriority", "PRIORITY_ORDER"]


class Priority(IntEnum):
    """Load priority for a context document.

    The integer value increases with "less important", so a cheaper document
    always has a larger ``Priority``. Comparisons (``<``) are therefore
    intuitive: ``P0 < P1 < ... < P4``.
    """

    #: Mandatory — always load for the matching task type.
    P0 = 0
    #: Directly relevant to the task at hand.
    P1 = 1
    #: Useful supporting material.
    P2 = 2
    #: Optional; load only if budget allows.
    P3 = 3
    #: Do not load unless explicitly required by the caller.
    P4 = 4


#: Ordered tuple, most-important first. Useful for iterating/budget trimming.
PRIORITY_ORDER: tuple[Priority, ...] = (
    Priority.P0,
    Priority.P1,
    Priority.P2,
    Priority.P3,
    Priority.P4,
)


class ContextPriority:
    """A named document descriptor paired with a load priority.

    Attributes
    ----------
    name:
        Stable key identifying the document/asset (e.g. ``SYSTEM_INDEX.md``
        or ``src.core.config``). Not a filesystem path.
    priority:
        The load priority for this doc under a given task type.
    reason:
        Short human-readable rationale, for auditability (Task 5 manifest).
    """

    __slots__ = ("name", "priority", "reason")

    def __init__(self, name: str, priority: Priority, reason: str) -> None:
        self.name = name
        self.priority = priority
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ContextPriority(name={self.name!r}, priority={self.priority.name}, reason={self.reason!r})"
