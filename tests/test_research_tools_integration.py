"""Integration tests for the Phase 3 research tools (real HTTP calls).

These tests are marked ``@pytest.mark.integration`` and are EXCLUDED from the
fast suite. They make REAL network calls to the public APIs and assert on
actual runtime responses — never fabricating success (SYSTEM_RULES §H.47-49,
PHASE 3 EXECUTION ADDENDUM §3/§4).

Run with:  python -m pytest tests/test_research_tools_integration.py -m integration -v

GRANULAR STATUS (Addendum §4):
  * Crossref / OpenAlex / PubMed — verified against real responses during Phase
    3 discovery; the tests below re-prove them and promote their status.
  * Semantic Scholar — repeatedly returned HTTP 429 (shared egress IP, no key)
    during discovery, so it is deliberately NOT asserted here and remains
    ``NOT_VERIFIED`` until a real run succeeds in this environment.
"""

from __future__ import annotations

import pytest

from src.core.status import IntegrationStatus
from src.tools.crossref import CrossrefTool
from src.tools.openalex import OpenAlexTool
from src.tools.pubmed import PubMedTool
from src.tools.research_tool import ResearchRequest

pytestmark = pytest.mark.integration


def _assert_usable_sources(tool: object, sources: list[object]) -> None:
    assert sources, f"{type(tool).__name__} returned zero sources"
    assert all(s.title for s in sources), "Every returned Source must have a title"


def test_crossref_real_search() -> None:
    """Real Crossref search; prove at least one titled Source is produced."""
    tool = CrossrefTool()
    request = ResearchRequest(query="deep learning", max_results=5)
    response = tool._execute(request)

    assert response.success is True
    _assert_usable_sources(tool, response.results)
    assert response.returned_count >= 1
    assert response.requested_max == 5
    # Provenance must be stamped on the Source, not just on the response.
    assert response.results[0].provenance is not None
    assert response.results[0].provenance.origin == "crossref"

    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED


def test_crossref_year_filter_passed_through() -> None:
    """Year filter must be encoded into the request (proven, not asserted on content)."""
    tool = CrossrefTool()
    request = ResearchRequest(query="deep learning", year_start=2018, year_end=2020, max_results=5)
    response = tool._execute(request)
    assert response.success is True
    # The filter is encoded as from-pub-date,until-pub-date (URL-encoded ``:`` → ``%3A``).
    assert "filter=from-pub-date%3A2018-01-01" in response.request_url
    assert "until-pub-date%3A2020-12-31" in response.request_url


def test_openalex_real_search() -> None:
    """Real OpenAlex search; prove at least one titled Source is produced."""
    tool = OpenAlexTool()
    request = ResearchRequest(query="deep learning", max_results=5)
    response = tool._execute(request)

    assert response.success is True
    _assert_usable_sources(tool, response.results)
    assert response.returned_count >= 1
    assert response.results[0].provenance.origin == "openalex"

    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED


def test_pubmed_real_search() -> None:
    """Real PubMed esearch+esummary; prove at least one titled Source is produced."""
    tool = PubMedTool()
    request = ResearchRequest(query="deep learning", max_results=5)
    response = tool._execute(request)

    assert response.success is True
    _assert_usable_sources(tool, response.results)
    assert response.returned_count >= 1
    assert response.results[0].provenance.origin == "pubmed"

    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED
