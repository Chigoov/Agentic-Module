"""Offline unit tests for OpenLibraryTool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.schemas.source import AccessMode, RightsStatus, SourceState, SourceType
from src.tools.http_client import HttpResult
from src.tools.open_library import OpenLibraryTool
from src.tools.research_tool import ResearchRequest


@pytest.fixture
def sample_open_library_payload() -> dict:
    return {
        "numFound": 2,
        "docs": [
            {
                "key": "/works/OL12345W",
                "title": "Public Domain Classic",
                "author_name": ["Author, Classic"],
                "first_publish_year": 1920,
                "publisher": ["Vintage Press"],
                "isbn": ["9780000000001"],
                "language": ["eng"],
                "subject": ["Literature", "History"],
                "ebook_access": "public",
                "ia": ["classicbook1920"],
            },
            {
                "key": "/works/OL67890W",
                "title": "Modern Protected Book",
                "author_name": ["Modern, Author"],
                "first_publish_year": 2018,
                "publisher": ["Commercial Academic Pub"],
                "isbn": ["9781111111111"],
                "ebook_access": "borrowable",
                "ia": ["modernbook2018"],
            },
        ],
    }


def test_open_library_public_book_allows_download(sample_open_library_payload: dict) -> None:
    tool = OpenLibraryTool()
    source = tool._item_to_source(sample_open_library_payload["docs"][0])

    assert source.title == "Public Domain Classic"
    assert source.authors == ["Author, Classic"]
    assert source.year == 1920
    assert source.publisher == "Vintage Press"
    assert source.isbn == "9780000000001"
    assert source.language == "eng"
    assert source.landing_url == "https://openlibrary.org/works/OL12345W"
    assert source.provider == "open_library"
    assert source.provider_record_id == "/works/OL12345W"
    assert source.source_type is SourceType.BOOK

    assert source.access_mode is AccessMode.OPEN_DOWNLOAD
    assert source.rights_status is RightsStatus.PUBLIC_DOMAIN
    assert source.download_allowed is True
    assert source.download_urls == ["https://archive.org/download/classicbook1920/classicbook1920.pdf"]


def test_open_library_borrowable_book_blocks_download(sample_open_library_payload: dict) -> None:
    tool = OpenLibraryTool()
    source = tool._item_to_source(sample_open_library_payload["docs"][1])

    assert source.title == "Modern Protected Book"
    assert source.access_mode is AccessMode.BORROW_ONLY
    assert source.rights_status is RightsStatus.RESTRICTED
    assert source.download_allowed is False
    assert source.download_urls == []


def test_open_library_search_offline_mock(sample_open_library_payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = OpenLibraryTool()
    mock_client = MagicMock()
    mock_client.get_json.return_value = HttpResult(
        url="https://openlibrary.org/search.json?q=test&limit=10",
        status=200,
        headers={"content-type": "application/json"},
        text=json.dumps(sample_open_library_payload),
    )
    monkeypatch.setattr(tool, "_client", lambda: mock_client)

    response = tool.execute(ResearchRequest(query="test", max_results=10))
    assert response.success is True
    assert response.result_count == 2
    assert response.results[0].state is SourceState.DISCOVERED
    assert response.results[0].title == "Public Domain Classic"
    assert response.results[1].access_mode is AccessMode.BORROW_ONLY
