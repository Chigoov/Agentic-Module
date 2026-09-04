"""Unit tests for research tools: base contract and provider parsers (no network)."""

from __future__ import annotations

import pytest

from src.tools.crossref import CrossrefTool
from src.tools.openalex import OpenAlexTool
from src.tools.pubmed import PubMedTool
from src.tools.research_tool import ResearchRequest, ResearchResponse
from src.tools.semantic_scholar import SemanticScholarTool


class TestResearchRequest:
    def test_defaults(self) -> None:
        req = ResearchRequest(query="deep learning")
        assert req.max_results == 25
        assert req.year_start is None
        assert req.year_end is None

    def test_max_results_bounds(self) -> None:
        with pytest.raises(Exception):
            ResearchRequest(query="x", max_results=0)
        with pytest.raises(Exception):
            ResearchRequest(query="x", max_results=500)


class TestResearchResponse:
    def test_preserves_limit_fields(self) -> None:
        resp = ResearchResponse(
            success=True,
            requested_max=25,
            raw_count=100,
            returned_count=100,
            local_truncation=True,
        )
        assert resp.requested_max == 25
        assert resp.raw_count == 100
        assert resp.returned_count == 100
        assert resp.local_truncation is True


class TestCrossrefParser:
    def test_item_to_source(self) -> None:
        tool = CrossrefTool()
        item = {
            "title": ["Deep Learning"],
            "author": [{"given": "Yann", "family": "LeCun"}],
            "issued": {"date-parts": [[2015, 5, 26]]},
            "container-title": ["Nature"],
            "DOI": "10.1038/nature14539",
            "URL": "https://doi.org/10.1038/nature14539",
            "type": "journal-article",
            "is-referenced-by-count": 84128,
        }
        source = tool._item_to_source(item)
        assert source.title == "Deep Learning"
        assert source.authors == ["Yann LeCun"]
        assert source.year == 2015
        assert source.venue == "Nature"
        assert source.doi == "10.1038/nature14539"
        assert source.citation_count == 84128


class TestOpenAlexParser:
    def test_item_to_source(self) -> None:
        tool = OpenAlexTool()
        item = {
            "title": "Deep learning",
            "authorships": [{"author": {"display_name": "Yann LeCun"}}],
            "publication_year": 2015,
            "primary_location": {
                "source": {"display_name": "Nature"},
                "landing_page_url": "https://doi.org/10.1038/nature14539",
            },
            "doi": "https://doi.org/10.1038/nature14539",
            "type": "article",
            "cited_by_count": 84128,
        }
        source = tool._item_to_source(item)
        assert source.title == "Deep learning"
        assert source.authors == ["Yann LeCun"]
        assert source.year == 2015
        assert source.venue == "Nature"
        assert source.doi == "10.1038/nature14539"
        assert source.citation_count == 84128


class TestSemanticScholarParser:
    def test_item_to_source(self) -> None:
        tool = SemanticScholarTool()
        item = {
            "title": "Deep learning",
            "authors": [{"name": "Yann LeCun"}],
            "year": 2015,
            "venue": "Nature",
            "externalIds": {"DOI": "10.1038/nature14539"},
            "url": "https://www.semanticscholar.org/paper/x",
            "abstract": "an abstract",
            "publicationTypes": ["JournalArticle"],
            "citationCount": 84128,
        }
        source = tool._item_to_source(item)
        assert source.title == "Deep learning"
        assert source.authors == ["Yann LeCun"]
        assert source.year == 2015
        assert source.venue == "Nature"
        assert source.doi == "10.1038/nature14539"
        assert source.citation_count == 84128


class TestPubMedParser:
    def test_year_from_pubdate(self) -> None:
        assert PubMedTool._year_from_pubdate("2026 Sep 1") == 2026
        assert PubMedTool._year_from_pubdate("2015") == 2015
        assert PubMedTool._year_from_pubdate("2015 Jan-Feb") == 2015
        assert PubMedTool._year_from_pubdate(None) is None

    def test_record_to_source(self) -> None:
        record = {
            "title": "Deep learning",
            "authors": [{"name": "LeCun Y"}, {"name": "Bengio Y"}],
            "pubdate": "2015 May 27",
            "fulljournalname": "Nature",
            "source": "Nature",
            "articleids": [
                {"idtype": "pubmed", "value": "26017442"},
                {"idtype": "doi", "value": "10.1038/nature14539"},
            ],
            "pubtype": ["Journal Article"],
        }
        source = PubMedTool()._record_to_source("26017442", record)
        assert source.title == "Deep learning"
        assert source.authors == ["LeCun Y", "Bengio Y"]
        assert source.year == 2015
        assert source.venue == "Nature"
        assert source.doi == "10.1038/nature14539"
        assert source.url == "https://pubmed.ncbi.nlm.nih.gov/26017442/"
