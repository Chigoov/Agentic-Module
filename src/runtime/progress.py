"""Progress event log for the local monitor."""

from __future__ import annotations

from datetime import UTC, datetime
from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from src.core.paths import get_paths
from src.core.storage import append_jsonl

__all__ = ["progress_file", "record_progress", "read_progress", "progress_scope", "progress_context"]

_context: ContextVar[dict[str, Any]] = ContextVar("aai_progress", default={})
_write_lock = Lock()


def progress_context() -> dict[str, Any]:
    return dict(_context.get())


@contextmanager
def progress_scope(**fields: Any):
    """Keep nested agent events in one job without sharing state across threads."""
    context = {"job_id": uuid4().hex, **_context.get(), **fields}
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


def progress_file(root: str | Path | None = None) -> Path:
    base = Path(root) if root else get_paths().state_dir
    return base / "progress.jsonl"


def record_progress(stage: str, status: str, *, message: str = "", **extra: Any) -> int:
    path = progress_file()
    with _write_lock:
        return append_jsonl(
            path,
            [{"time": datetime.now(UTC).isoformat(), "stage": stage, "status": status, "message": message, **_context.get(), **extra}],
            root=path.parent,
        )


def read_progress(root: str | Path | None = None, *, limit: int | None = 100, job_id: str | None = None) -> list[dict[str, Any]]:
    path = progress_file(root)
    if not path.is_file():
        return []
    # ponytail: scan the append-only log; use a per-job index if history grows large.
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    events = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not line.endswith("\n"):
                break  # Another process can still be writing its final line.
            raise
        if job_id is None or event.get("job_id") == job_id:
            events.append(event)
    return events[-limit:] if limit is not None else events
