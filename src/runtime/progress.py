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
    if limit is not None and limit <= 0:
        return []
    events = []
    # ponytail: bounded reverse tail; rare jobs may scan farther, add an index only if measured necessary.
    with path.open("rb") as stream:
        stream.seek(0, 2)
        position = stream.tell()
        pending = b""
        first = True
        while position:
            size = min(position, 65536)
            position -= size
            stream.seek(position)
            lines = (stream.read(size) + pending).split(b"\n")
            pending = lines.pop(0)
            for line in reversed(lines):
                if first:
                    first = False
                    # An unfinished final line belongs to a concurrent writer.
                    if line:
                        continue
                if not line.strip():
                    continue
                event = json.loads(line)
                if job_id is None or event.get("job_id") == job_id:
                    events.append(event)
                    if limit is not None and len(events) >= limit:
                        return list(reversed(events))
        if pending.strip() and not first:
            event = json.loads(pending)
            if job_id is None or event.get("job_id") == job_id:
                events.append(event)
    return list(reversed(events))


def progress_since(root=None, *, offset=0):
    """Read complete appended records and retain the unfinished-line offset."""
    path = progress_file(root)
    if not path.exists():
        return [], 0
    events = []
    with path.open("rb") as stream:
        if offset > stream.seek(0, 2):
            offset = 0
        stream.seek(offset)
        while line := stream.readline():
            if not line.endswith(b"\n"):
                break
            if line.strip():
                events.append(json.loads(line))
            offset = stream.tell()
    return events, offset
