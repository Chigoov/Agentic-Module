"""Progress event log for the local monitor."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.paths import get_paths
from src.core.storage import append_jsonl, read_jsonl

__all__ = ["progress_file", "record_progress", "read_progress"]


def progress_file(root: str | Path | None = None) -> Path:
    base = Path(root) if root else get_paths().state_dir
    return base / "progress.jsonl"


def record_progress(stage: str, status: str, *, message: str = "", **extra: Any) -> int:
    path = progress_file()
    return append_jsonl(
        path,
        [{"time": datetime.now(UTC).isoformat(), "stage": stage, "status": status, "message": message, **extra}],
        root=path.parent,
    )


def read_progress(root: str | Path | None = None, *, limit: int = 100) -> list[dict[str, Any]]:
    return read_jsonl(progress_file(root))[-limit:]
