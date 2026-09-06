"""Fast tests for roadmap Phase 9 routing telemetry."""

from __future__ import annotations

from src.core.storage import read_jsonl
from src.routing.telemetry import record_model_telemetry


def test_model_telemetry_appends_jsonl(tmp_path) -> None:
    path = tmp_path / "model_telemetry.jsonl"
    written = record_model_telemetry(
        path,
        root=tmp_path,
        capability="writing",
        status="PENDING_CONFIGURATION",
        error_code="PENDING_CONFIGURATION",
    )
    assert written == 1
    assert read_jsonl(path)[0]["capability"] == "writing"
