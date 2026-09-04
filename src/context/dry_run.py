"""Context Intelligence integration dry-run harness (execution boundary).

This module is the first **real execution** of the context-selection layer
(Tasks 3-7), not merely a unit test. Given a task description it:

1. classifies the task (deterministic, rule-based);
2. builds the candidate pool from actual repository file sizes;
3. assigns explicit per-task priorities (relevant → P0/P1/P2, all else → P4);
4. selects the minimum relevant context via :class:`ContextLoader`, enforcing
   the category budget;
5. records a :class:`ContextManifest` per task.

It is wired as an analysable CLI/entry point so the integration is actually
exercised. It does **not** call an LLM, and it does **not** claim measured
token savings — only *estimated* context reduction. Real token reduction
requires configured providers + telemetry (still pending).

Usage (from DATA BASE/):
    python -m src.context.dry_run --task "fix the bug in this code"
    python -m src.context.dry_run --all
    python -m src.context.dry_run --all --budget 12000
    python -m src.context.dry_run --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from src.context.budget import budget_for
from src.context.classifier import TaskCategory, classify_task
from src.context.loader import ContextDocument, ContextLoader
from src.context.manifest import ContextManifest
from src.context.priority import Priority

__all__ = [
    "build_candidate_pool",
    "run_dry_run",
    "report_reduction",
    "format_report",
    "main",
    "EXAMPLES",
]


# --------------------------------------------------------------------------- #
# Candidate pool (real repository files, measured sizes)
# --------------------------------------------------------------------------- #
_CANDIDATE_PATHS: tuple[tuple[str, str], ...] = (
    ("00_MASTER_INSTRUCTION.md", "00_MASTER_INSTRUCTION.md"),
    ("AGENT_CONSTITUTION.md", "AGENT_CONSTITUTION.md"),
    ("ARCHITECTURE.md", "ARCHITECTURE.md"),
    ("BUILD_PLAN.md", "BUILD_PLAN.md"),
    ("ENGINEERING_PROTOCOL.md", "ENGINEERING_PROTOCOL.md"),
    ("README.md", "README.md"),
    ("SYSTEM_INDEX.md", "SYSTEM_INDEX.md"),
    ("SYSTEM_RULES.md", "SYSTEM_RULES.md"),
    ("WORKFLOW.md", "WORKFLOW.md"),
    ("docs/PHASE_1_REPORT.md", "docs/PHASE_1_REPORT.md"),
    ("docs/PHASE_2_REPORT.md", "docs/PHASE_2_REPORT.md"),
    ("docs/RENCANA_FASE_3.md", "docs/RENCANA_FASE_3.md"),
    ("docs/LAPORAN_FASE_2.md", "docs/LAPORAN_FASE_2.md"),
    ("src/__init__.py", "src/__init__.py"),
    ("src/core/config.py", "src/core/config.py"),
    ("src/core/paths.py", "src/core/paths.py"),
    ("src/core/project_manager.py", "src/core/project_manager.py"),
    ("src/core/storage.py", "src/core/storage.py"),
    ("src/context/classifier.py", "src/context/classifier.py"),
    ("src/context/loader.py", "src/context/loader.py"),
    ("src/tools/publish_or_perish.py", "src/tools/publish_or_perish.py"),
    ("src/tools/research_tool.py", "src/tools/research_tool.py"),
    ("src/tools/source_mapper.py", "src/tools/source_mapper.py"),
    ("src/schemas/source.py", "src/schemas/source.py"),
    ("src/schemas/claim.py", "src/schemas/claim.py"),
    ("src/schemas/evidence.py", "src/schemas/evidence.py"),
    ("src/schemas/task.py", "src/schemas/task.py"),
    ("tests/test_schemas.py", "tests/test_schemas.py"),
    ("tests/test_tools.py", "tests/test_tools.py"),
    ("tests/test_source_mapper.py", "tests/test_source_mapper.py"),
    ("tests/test_research_tools.py", "tests/test_research_tools.py"),
    ("tests/test_storage.py", "tests/test_storage.py"),
)


def _read_size(path: str) -> int:
    """Return a file's size in bytes, or 0 when missing (defensive)."""
    try:
        with open(path, "rb") as stream:
            return len(stream.read())
    except OSError:
        return 0


def build_candidate_pool() -> list[ContextDocument]:
    """Build the real candidate pool, sized from the live filesystem.

    Priority is assigned per-task by :class:`_RelevantMap`; here docs are given
    a placeholder so the pool itself is always sizeable/importable.
    """
    pool: list[ContextDocument] = []
    for display, path in _CANDIDATE_PATHS:
        pool.append(
            ContextDocument(
                name=display,
                size_bytes=_read_size(path),
                priority=Priority.P2,
                reason="candidate",
            )
        )
    return pool


# --------------------------------------------------------------------------- #
# Per-task relevant-set policy
# --------------------------------------------------------------------------- #
#: For each task category, which documents are RELEVANT and at what priority.
#: Anything NOT in this map is assigned P4 (not loaded unless required), so a
#: task genuinely loads only its minimum relevant context.
_RELEVANT: dict[TaskCategory, dict[str, tuple[Priority, str]]] = {
    TaskCategory.SIMPLE_CODE: {
        "src/core/config.py": (Priority.P0, "Config the code change touches."),
        "src/core/paths.py": (Priority.P0, "Path resolution for the touched module."),
        "src/core/storage.py": (Priority.P1, "Storage primitives used by the change."),
        "tests/test_storage.py": (Priority.P1, "Regression test for the storage change."),
        "src/core/errors.py": (Priority.P2, "Error contract in scope."),
        "SYSTEM_RULES.md": (Priority.P2, "Minimal engineering rules."),
        "ENGINEERING_PROTOCOL.md": (Priority.P2, "Minimal process rules."),
    },
    TaskCategory.ARCHITECTURE: {
        "SYSTEM_INDEX.md": (Priority.P0, "Navigation; read first for architecture."),
        "ENGINEERING_PROTOCOL.md": (Priority.P0, "Golden rule: architecture review first."),
        "ARCHITECTURE.md": (Priority.P0, "Layered architecture authority."),
        "AGENT_CONSTITUTION.md": (Priority.P1, "Immutable rules for architectural decisions."),
        "00_MASTER_INSTRUCTION.md": (Priority.P1, "System identity and filesystem rules."),
        "SYSTEM_RULES.md": (Priority.P2, "Operational rules."),
        "BUILD_PLAN.md": (Priority.P2, "Phase sequencing."),
    },
    TaskCategory.RESEARCH: {
        "AGENT_CONSTITUTION.md": (Priority.P0, "Academic integrity and evidence policy."),
        "WORKFLOW.md": (Priority.P0, "Research lifecycle and state machines."),
        "ARCHITECTURE.md": (Priority.P1, "Tool/agent layering."),
        "src/tools/publish_or_perish.py": (Priority.P1, "Primary evidence-discovery tool."),
        "src/tools/research_tool.py": (Priority.P1, "Research tool interface."),
        "src/tools/source_mapper.py": (Priority.P1, "Source normalization."),
        "src/schemas/source.py": (Priority.P1, "Source record contract."),
        "src/schemas/evidence.py": (Priority.P1, "Evidence record contract."),
        "src/schemas/claim.py": (Priority.P2, "Claim-support contract."),
    },
}


def _priority_for(name: str, category: TaskCategory) -> tuple[Priority, str]:
    """Return (priority, reason) for a doc under a task category.

    Documents not in the relevant map are P4 (not loaded unless required).
    Historical ``docs/`` are always P4 (the "irrelevant historical docs"
    exclusion target).
    """
    if name.startswith("docs/"):
        return Priority.P4, "Historical report; not relevant to this task."
    relevant = _RELEVANT.get(category, {})
    if name in relevant:
        return relevant[name]
    return Priority.P4, "Not part of this task's minimum relevant context."


# --------------------------------------------------------------------------- #
# Task examples
# --------------------------------------------------------------------------- #
#: Unambiguous prompts for the three required task types.
EXAMPLES: tuple[tuple[str, str], tuple[str, str], tuple[str, str]] = (
    ("SIMPLE_CODE", "implement a helper function in the src/core/storage module"),
    ("ARCHITECTURE", "refactor the repository layering for modularity and dependency direction"),
    ("RESEARCH", "search for sources about machine learning with crossref"),
)


# --------------------------------------------------------------------------- #
# Dry-run execution
# --------------------------------------------------------------------------- #
def run_dry_run(
    task_text: str,
    *,
    task_id: str | None = None,
    budget: int | None = None,
    pool: Sequence[ContextDocument] | None = None,
) -> ContextManifest:
    """Classify a task and select its minimum context, returning the manifest.

    This is the **real execution path**: classification → candidate pool →
    per-task priority → context selection → manifest. It never calls an LLM.
    """
    category = classify_task(task_text)
    effective_id = task_id or f"dry_{category.value.lower()}"

    candidates = list(pool) if pool is not None else build_candidate_pool()

    # Apply per-task priorities; non-relevant docs become P4 (excluded).
    prepared: list[ContextDocument] = []
    for doc in candidates:
        prio, reason = _priority_for(doc.name, category)
        prepared.append(ContextDocument(doc.name, doc.size_bytes, prio, reason))

    # Enforce the category budget by default (Task 6), overridable per-call.
    effective_budget = budget if budget is not None else budget_for(category)

    loader = ContextLoader(budget=effective_budget)
    return loader.select(
        task_type=category,
        task_id=effective_id,
        candidates=prepared,
        task_target=task_text,
        exclude_p4=True,
    )


def report_reduction(manifest: ContextManifest, naive: int) -> dict[str, int | float]:
    """Compute ESTIMATED context reduction vs a naive full-load baseline.

    IMPORTANT: this is an ESTIMATED reduction from selective loading, NOT a
    measured LLM token saving. Measured savings require real provider calls and
    telemetry (model routing is still PENDING_CONFIGURATION).
    """
    after = manifest.estimated_context_tokens
    reduction = max(0, naive - after)
    pct = (reduction / naive * 100) if naive else 0.0
    return {
        "naive_before": naive,
        "selected_after": after,
        "reduction_tokens": reduction,
        "reduction_pct": round(pct, 1),
    }


def format_report(manifest: ContextManifest) -> str:
    """Render a human-friendly report for one dry-run task."""
    lines: list[str] = []
    lines.append(f"Task ID          : {manifest.task_id}")
    lines.append(f"Task type        : {manifest.task_type.value}")
    lines.append(f"Task target      : {manifest.task_target or '-'}")
    lines.append(f"Budget           : {manifest.budget_tokens or 'unlimited'}")
    lines.append(f"Over budget?     : {manifest.over_budget}")
    lines.append(f"Selected files   : {len(manifest.files_selected)}")
    lines.append(f"Skipped files    : {len(manifest.files_skipped)}")
    lines.append(f"Est. context     : {manifest.estimated_context_tokens} tokens")
    lines.append("--- Selected (priority | tokens | name) ---")
    for entry in manifest.entries:
        if entry.selected:
            lines.append(f"  P{entry.priority.name[1]} | {entry.tokens:>5} | {entry.name}")
    lines.append("--- Skipped (priority | tokens | name | reason) ---")
    for entry in manifest.entries:
        if not entry.selected:
            lines.append(f"  P{entry.priority.name[1]} | {entry.tokens:>5} | {entry.name} | {entry.reason}")
    return "\n".join(lines)


def _naive_before(pool: Sequence[ContextDocument]) -> int:
    """Estimate context if EVERYTHING were loaded (the naive baseline)."""
    return sum(doc.estimated_tokens for doc in pool)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the context dry-run harness."""
    parser = argparse.ArgumentParser(description="Context Intelligence integration dry-run")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--task", type=str, help="A task description to classify & select context for.")
    group.add_argument("--all", action="store_true", help="Run the three preset task examples.")
    parser.add_argument("--task-id", type=str, default=None, help="Optional task id.")
    parser.add_argument("--budget", type=int, default=None, help="Override the context budget (tokens).")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    pool = build_candidate_pool()
    naive = _naive_before(pool)

    if args.all:
        tasks: list[tuple[str, str]] = list(EXAMPLES)
    elif args.task:
        tasks = [(args.task, args.task)]
    else:
        print(__doc__)
        return 0

    outputs = []
    for label, text in tasks:
        manifest = run_dry_run(text, task_id=args.task_id or f"dry_{label.lower()}", budget=args.budget, pool=pool)
        outputs.append((manifest, report_reduction(manifest, naive)))

    if args.json:
        payload = {
            "note": "ESTIMATED context reduction only — NOT measured LLM token savings (model routing = PENDING_CONFIGURATION).",
            "naive_before_tokens": naive,
            "results": [
                {"manifest": m.to_dict(), "estimated_reduction": red} for m, red in outputs
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for m, red in outputs:
            print(format_report(m))
            print(f"Est. context BEFORE filtering : {red['naive_before']} tokens (naive full load)")
            print(f"Est. context AFTER filtering  : {red['selected_after']} tokens (minimum relevant)")
            print(f"ESTIMATED context reduction   : {red['reduction_tokens']} tokens ({red['reduction_pct']}%)")
            print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
