"""Offline unit tests for DOABTool (Directory of Open Access Books)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.schemas.source import AccessMode, RightsStatus, SourceState, SourceType
from src.tools.doab import DOABTool
from src.tools.http_client import HttpResult
from src.tools.research_tool import ResearchRequest


@pytest.fixture
def sample_doab_payload() -> list[dict]:
    return [
        {
            "uuid": "0152be55-1b7e-47b9-864c-16b1056b59de",
            "handle": "20.500.12854/146036",
            "metadata": [
                {"key": "dc.title", "value": "Climate Security and Climate Justice"},
                {"key": "dc.contributor.author", "value": "Benjaminsen, Tor A."},
                {"key": "dc.contributor.author", "value": "Svarstad, Hanne"},
                {"key": "dc.date.issued", "value": "2024-09-17"},
                {"key": "dc.identifier.uri", "value": "https://directory.doabooks.org/handle/20.500.12854/146036"},
                {"key": "oapen.identifier.doi", "value": "10.4337/9781035325184"},
                {"key": "dc.identifier.isbn", "value": "9781035325184"},
                {"key": "publisher.name", "value": "Edward Elgar Publishing"},
                {"key": "dc.language", "value": "English"},
                {"key": "dc.subject.classification", "value": "RNPG"},
                {"key": "dc.subject.other", "value": "Environmental Law"},
                {"key": "dc.description.abstract", "value": "A comprehensive open access book on climate security."},
                {"key": "publisher.oalicense", "value": "Published with a creative commons BY license. http://creativecommons.org/licenses/by/4.0/"},
                {"key": "dc.rights.uri", "value": "http://creativecommons.org/licenses/by/4.0/"},
            ],
            "bitstreams": [
                {
                    "uuid": "c029fc68-c684-4b4b-b92a-00b2780f7b05",
                    "name": "thumbnail.png",
                    "bundleName": "THUMBNAIL",
                    "mimeType": "image/png",
                    "retrieveLink": "/rest/bitstreams/c029fc68-c684-4b4b-b92a-00b2780f7b05/retrieve",
                },
                {
                    "uuid": "5988ddfa-62f2-48a6-a71f-72af3125d215",
                    "name": "book.pdf",
                    "bundleName": "ORIGINAL",
                    "mimeType": "application/pdf",
                    "retrieveLink": "/rest/bitstreams/5988ddfa-62f2-48a6-a71f-72af3125d215/retrieve",
                },
            ],
        },
        {
            "uuid": "restricted-book-uuid",
            "handle": "20.500.12854/99999",
            "metadata": [
                {"key": "dc.title", "value": "Restricted Metadata Only Book"},
                {"key": "dc.contributor.author", "value": "Author, Closed"},
                {"key": "dc.date.issued", "value": "2019"},
                {"key": "publisher.name", "value": "Strict Publisher"},
            ],
            "bitstreams": [],
        },
    ]


def test_doab_item_to_source_mapping(sample_doab_payload: list[dict]) -> None:
    tool = DOABTool()
    source = tool._item_to_source(sample_doab_payload[0])

    assert source.title == "Climate Security and Climate Justice"
    assert source.authors == ["Benjaminsen, Tor A.", "Svarstad, Hanne"]
    assert source.year == 2024
    assert source.publisher == "Edward Elgar Publishing"
    assert source.venue == "Edward Elgar Publishing"
    assert source.doi == "10.4337/9781035325184"
    assert source.isbn == "9781035325184"
    assert source.language == "English"
    assert source.landing_url == "https://directory.doabooks.org/handle/20.500.12854/146036"
    assert source.url == "https://directory.doabooks.org/handle/20.500.12854/146036"
    assert source.abstract == "A comprehensive open access book on climate security."
    assert source.source_type is SourceType.BOOK
    assert source.provider == "doab"
    assert source.provider_record_id == "0152be55-1b7e-47b9-864c-16b1056b59de"

    # Rights & Access checks
    assert source.rights_status is RightsStatus.OPEN_LICENSE
    assert source.access_mode is AccessMode.OPEN_DOWNLOAD
    assert source.download_allowed is True
    assert len(source.download_urls) == 1
    assert source.download_urls[0] == "https://directory.doabooks.org/rest/bitstreams/5988ddfa-62f2-48a6-a71f-72af3125d215/retrieve"

    # Preserves extra fields in metadata
    assert "RNPG" in source.metadata["subject"]
    assert "Environmental Law" in source.metadata["subject"]
    assert source.metadata["handle"] == "20.500.12854/146036"


def test_doab_restricted_item_has_no_download(sample_doab_payload: list[dict]) -> None:
    tool = DOABTool()
    source = tool._item_to_source(sample_doab_payload[1])

    assert source.title == "Restricted Metadata Only Book"
    assert source.download_allowed is False
    assert source.download_urls == []
    assert source.access_mode is AccessMode.UNKNOWN
    assert source.rights_status is RightsStatus.UNKNOWN


def test_doab_search_offline_mock(sample_doab_payload: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    tool = DOABTool()
    mock_client = MagicMock()
    mock_client.get_json.return_value = HttpResult(
        url="https://directory.doabooks.org/rest/search?query=climate&limit=10&expand=metadata,bitstreams",
        status=200,
        headers={"content-type": "application/json"},
        text=json.dumps(sample_doab_payload),
    )
    monkeypatch.setattr(tool, "_client", lambda: mock_client)

    response = tool.execute(ResearchRequest(query="climate", max_results=10))
    assert response.success is True
    assert response.result_count == 2
    assert response.results[0].title == "Climate Security and Climate Justice"
    assert response.results[0].source_type is SourceType.BOOK
    assert response.results[0].state is SourceState.DISCOVERED


def test_doab_search_year_filter_offline(sample_doab_payload: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    tool = DOABTool()
    mock_client = MagicMock()
    mock_client.get_json.return_value = HttpResult(
        url="https://directory.doabooks.org/rest/search",
        status=200,
        headers={"content-type": "application/json"},
        text=json.dumps(sample_doab_payload),
    )
    monkeypatch.setattr(tool, "_client", lambda: mock_client)

    # Filter for year >= 2020
    response = tool.execute(ResearchRequest(query="climate", year_start=2020))
    assert response.success is True
    assert response.result_count == 1
    assert response.results[0].year == 2024
