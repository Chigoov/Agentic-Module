"""Minimal model-routing telemetry for roadmap Phase 9."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.storage import append_jsonl

__all__ = ["record_model_telemetry"]


def record_model_telemetry(
    path: str | Path,
    *,
    root: str | Path,
    capability: str,
    status: str,
    model_used: str = "",
    tokens_used: int = 0,
    error_code: str | None = None,
) -> int:
    """Append one model-routing telemetry event."""
    record: dict[str, Any] = {
        "capability": capability,
        "status": status,
        "model_used": model_used,
        "tokens_used": tokens_used,
        "error_code": error_code,
    }
    return append_jsonl(path, [record], root=root)
