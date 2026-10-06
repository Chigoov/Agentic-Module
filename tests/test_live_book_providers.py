"""Live integration tests for DOAB and Open Library providers.

These tests execute REAL HTTP calls to the official public endpoints and are
marked with @pytest.mark.integration.

Run separately via:
    python -m pytest -q tests/test_live_book_providers.py -m integration -v
"""

from __future__ import annotations

import pytest

from src.core.status import IntegrationStatus
from src.schemas.source import AccessMode, RightsStatus
from src.tools.doab import DOABTool
from src.tools.open_library import OpenLibraryTool
from src.tools.research_tool import ResearchRequest

pytestmark = pytest.mark.integration


def test_doab_live_search() -> None:
    """Live search test against DOAB official REST API.

    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.9
    """
    tool = DOABTool()
    assert tool.status() in {IntegrationStatus.CONFIGURED, IntegrationStatus.VERIFIED}

    request = ResearchRequest(
        query="climate justice",
        max_results=3,
        timeout_seconds=30,
    )
    response = tool.execute(request)

    # 1. Endpoint and response validation (HTTP status code 200, non-empty raw_response_text)
    assert response.request_url.startswith("https://directory.doabooks.org/rest/search")
    assert response.success is True, f"DOAB live request failed: {response.error_message}"
    assert response.http_status == 200, f"Expected HTTP status code 200, got {response.http_status}"
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    assert response.raw_response_text != "", "Raw response body must not be empty"

    # 2. Result count and minimum validity
    assert len(response.results) >= 1, "DOAB returned 0 results for query 'climate justice'"
    assert all(s.title and s.title.strip() for s in response.results), "Every DOAB source must have a real title"

    # 3. Provider origin and provenance
    for source in response.results:
        assert source.provider == "doab"
        assert source.provenance is not None
        assert source.provenance.origin == "doab"
        assert source.title and source.title.strip(), "Source title must be non-empty"

    first = response.results[0]
    assert first.provider == "doab"
    assert first.provenance is not None
    assert first.provenance.origin == "doab"

    # 4. Download URL provenance check
    for source in response.results:
        for dl_url in source.download_urls:
            assert dl_url.startswith("https://directory.doabooks.org/rest/bitstreams/"), (
                f"Unexpected download URL format: {dl_url}"
            )
            # URL bitstream identifier must be grounded in raw response text
            bitstream_id = dl_url.split("/bitstreams/")[1].split("/")[0]
            assert bitstream_id in response.raw_response_text, f"Bitstream ID {bitstream_id} not grounded in raw response"

    # 5. Honest status promotion on proven run
    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED


def test_open_library_live_search() -> None:
    """Live search test against Open Library search.json API.

    Validates: Requirements 2.1, 2.5, 2.6, 2.7, 2.8, 2.9
    """
    tool = OpenLibraryTool()
    assert tool.status() in {IntegrationStatus.CONFIGURED, IntegrationStatus.VERIFIED}

    request = ResearchRequest(
        query="climate change",
        max_results=3,
        timeout_seconds=30,
    )
    response = tool.execute(request)

    # 1. Endpoint and response validation (HTTP status code 200, non-empty raw_response_text)
    assert response.request_url.startswith("https://openlibrary.org/search.json")
    assert response.success is True, f"Open Library live request failed: {response.error_message}"
    assert response.http_status == 200, f"Expected HTTP status code 200, got {response.http_status}"
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    assert response.raw_response_text != "", "Raw response body must not be empty"

    # 2. Result count and minimum validity
    assert len(response.results) >= 1, "Open Library returned 0 results for 'climate change'"
    assert all(s.title and s.title.strip() for s in response.results), "Every Open Library source must have a title"

    # 3. Provider origin and provenance
    for source in response.results:
        assert source.provider == "open_library"
        assert source.provenance is not None
        assert source.provenance.origin == "open_library"
        assert source.title and source.title.strip(), "Source title must be non-empty"

    first = response.results[0]
    assert first.provider == "open_library"
    assert first.provenance is not None
    assert first.provenance.origin == "open_library"

    # 4. Strict borrowable rights check
    for source in response.results:
        ebook_acc = str(source.metadata.get("ebook_access") or "").lower()
        if ebook_acc in {"borrowable", "borrow", "inlibrary"}:
            assert source.access_mode is AccessMode.BORROW_ONLY
            assert source.download_allowed is False
            assert source.download_urls == []
        elif ebook_acc == "public":
            assert source.access_mode is AccessMode.OPEN_DOWNLOAD
            assert source.rights_status is RightsStatus.PUBLIC_DOMAIN
            assert source.download_allowed is True
            assert bool(source.download_urls)

    # 5. Honest status promotion on proven run
    tool.mark_verified()
    assert tool.status() is IntegrationStatus.VERIFIED
