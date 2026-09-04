"""Deterministic task classification (Task 3).

Classifies a user task into a category using **rule-based** heuristics so that
a cheap, fast path can select context without paying for an LLM call. An LLM
should only be consulted for genuinely ambiguous tasks (which map to
``UNKNOWN``).

The classifier is intentionally pure and dependency-free: it receives a text
and returns a category, so it can be unit-tested exhaustively.
"""

from __future__ import annotations

import re

from enum import StrEnum

__all__ = ["TaskCategory", "classify_task", "DEFAULT_KEYWORDS"]


class TaskCategory(StrEnum):
    """Deterministic categories the classifier can emit."""

    FILE_OPERATION = "FILE_OPERATION"
    SIMPLE_CODE = "SIMPLE_CODE"
    DEBUGGING = "DEBUGGING"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    RESEARCH = "RESEARCH"
    VERIFICATION = "VERIFICATION"
    EVIDENCE = "EVIDENCE"
    WRITING = "WRITING"
    AUDIT = "AUDIT"
    UNKNOWN = "UNKNOWN"


#: Keyword → category rules. Iterated in order so that the **first** match wins.
#: More specific/signalling categories come first; generic ones last.
DEFAULT_KEYWORDS: tuple[tuple[TaskCategory, tuple[str, ...]], ...] = (
    (
        TaskCategory.AUDIT,
        (
            "audit",
            "auditing",
            "audit arsitektur",
            "review the repository",
            "architecture audit",
            "code review",
            "security audit",
        ),
    ),
    (
        TaskCategory.ARCHITECTURE,
        (
            "architecture",
            "refactor",
            "refactoring",
            "layering",
            "monolithic",
            "modularity",
            "dependency direction",
            "separation of concerns",
        ),
    ),
    (
        TaskCategory.DEBUGGING,
        (
            "debug",
            "bug",
            "error",
            "traceback",
            "crash",
            "root cause",
            "stack trace",
            "fail",
            "regression",
        ),
    ),
    (
        TaskCategory.TESTING,
        (
            "test",
            "pytest",
            "unit test",
            "coverage",
            "test suite",
            "smoke test",
        ),
    ),
    (
        TaskCategory.DOCUMENTATION,
        (
            "documentation",
            "readme",
            "docs",
            "comment",
            "docstring",
            "changelog",
            "write up",
            "explain how",
            "how does x work",
        ),
    ),
    (
        TaskCategory.VERIFICATION,
        (
            "verify",
            "verification",
            "check the source",
            "confirm existence",
            "corroborate",
            "doi",
        ),
    ),
    (
        TaskCategory.FILE_OPERATION,
        (
            "create file",
            "rename",
            "move file",
            "delete file",
            "touch",
            "mkdir",
            "edit file",
            "add file",
        ),
    ),
    (
        TaskCategory.EVIDENCE,
        (
            "evidence",
            "extract evidence",
            "claim support",
            "overclaiming",
            "mapping claim",
        ),
    ),
    (
        TaskCategory.WRITING,
        (
            "write",
            "prose",
            "draft",
            "essay",
            "paragraph",
            "outline",
            "synthesize",
        ),
    ),
    (
        TaskCategory.RESEARCH,
        (
            "research",
            "search",
            "discovery",
            "candidate",
            "source",
            "reference",
            "citation",
            "publish or perish",
            "crossref",
            "semantic scholar",
        ),
    ),
    (
        TaskCategory.SIMPLE_CODE,
        (
            "code",
            "function",
            "implement",
            "fix",
            "add logic",
            "refactor code",
            "method",
            "class",
        ),
    ),
)


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def classify_task(text: str, *, keywords: tuple[tuple[TaskCategory, tuple[str, ...]], ...] | None = None) -> TaskCategory:
    """Classify ``text`` into a :class:`TaskCategory`.

    Parameters
    ----------
    text:
        The user task description.
    keywords:
        Optional override of the keyword rules. When ``None``,
        :data:`DEFAULT_KEYWORDS` is used.

    Returns
    -------
    TaskCategory
        ``UNKNOWN`` when no rule matches.

    Notes
    -----
    Matching is rule-based and deterministic. The first rule whose keyword
    appears in the normalized text wins. Rules are ordered most-specific
    first so e.g. "audit" beats a generic "code" match.
    """
    if not text:
        return TaskCategory.UNKNOWN
    normalized = _normalize(text)
    if not normalized:
        return TaskCategory.UNKNOWN

    rules = keywords if keywords is not None else DEFAULT_KEYWORDS
    for category, words in rules:
        if any(word in normalized for word in words):
            return category
    return TaskCategory.UNKNOWN
