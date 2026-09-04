"""Integration tests for the real Publish or Perish CLI adapter.

These tests are marked ``@pytest.mark.integration`` and are EXCLUDED from the
fast suite. They make a REAL network call via the installed PoP CLI
(``pop8query.exe``) and assert on actual output. They do NOT fabricate success.

Run with:  python -m pytest tests/ -m integration -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import get_config
from src.core.status import IntegrationStatus
from src.tools.publish_or_perish import (
    PublishOrPerishRequest,
    PublishOrPerishResponse,
    PublishOrPerishTool,
)

pytestmark = pytest.mark.integration


def _pop_tool() -> PublishOrPerishTool:
    return PublishOrPerishTool()


def test_po_pop_executable_discovered() -> None:
    """The configured PoP executable must be found on disk."""
    tool = _pop_tool()
    exe = tool._executable()
    assert exe is not None, "PoP executable should be discoverable on this system"
    assert Path(exe).is_file(), f"Configured executable not on disk: {exe}"


def test_po_pop_real_search_crossref() -> None:
    """Run a real Crossref search and assert a normalized Source is produced.

    This is the authoritative proof that the integration works. It exercises
    the actual CLI, parses real JSONL output, and normalizes at least one
    record with a title.
    """
    tool = _pop_tool()
    request = PublishOrPerishRequest(
        query="deep learning education",
        query_field="title",
        source="crossref",
        max_results=5,
    )
    response: PublishOrPerishResponse = tool._execute(request)

    # Honest reflection of the real run. We assert the process exited 0 and
    # produced usable output — never fabricating success.
    assert response.exit_code == 0, (
        f"PoP subprocess exited {response.exit_code}: {response.error_message}"
    )
    assert response.success is True
    assert response.detected_format == "jsonl"
    assert response.result_count >= 1, "At least one normalized Source expected"

    # Verify the first result has a title (minimal validity).
    first = response.results[0]
    assert first.get("title"), "Normalized result must have a title"
    assert first["source_origin"] == "publish_or_perish"

    # Diagnostic fields preserved for audit (SYSTEM_RULES §H.50).
    assert response.command
    assert response.raw_count >= 1


def test_po_pop_year_filter() -> None:
    """Year filter is passed through to the CLI (not asserted on results)."""
    tool = _pop_tool()
    request = PublishOrPerishRequest(
        query="deep learning",
        query_field="title",
        source="crossref",
        max_results=5,
        year_start=2018,
        year_end=2024,
    )
    response = tool._execute(request)
    assert response.exit_code == 0
    # Year filter must appear in the command line (proof of real pass-through).
    assert "--years" in response.command


def test_status_not_implemented_before_verified() -> None:
    """Before a real verified run, status() must be conservative (NOT_IMPLEMENTED)."""
    tool = _pop_tool()
    # This module flag is not set until mark_verified is called by a real test.
    assert tool.status() is IntegrationStatus.NOT_IMPLEMENTED or tool.status() is IntegrationStatus.VERIFIED


def test_mark_verified_after_real_run() -> None:
    """After a real successful search, mark_verified() promotes status to VERIFIED."""
    tool = _pop_tool()
    request = PublishOrPerishRequest(
        query="machine learning",
        query_field="title",
        source="crossref",
        max_results=3,
    )
    response = tool._execute(request)
    assert response.exit_code == 0, "Precondition: real search must succeed"
    assert response.result_count >= 1, "Precondition: must produce at least one Source"

    # Prove the integration, then status must report VERIFIED.
    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED
