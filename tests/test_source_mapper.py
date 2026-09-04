"""Unit tests for the provider → Source mapping layer (pure, no I/O)."""

from __future__ import annotations

import pytest

from src.schemas.source import Source, SourceType
from src.tools.source_mapper import (
    coerce_source_type,
    coerce_year,
    normalize_authors,
    normalize_doi,
    normalize_title,
    source_from_dict,
)


class TestNormalizeDoi:
    def test_strips_doi_prefixes(self) -> None:
        assert normalize_doi("https://doi.org/10.1038/nature14539") == "10.1038/nature14539"
        assert normalize_doi("http://dx.doi.org/10.1038/nature14539") == "10.1038/nature14539"
        assert normalize_doi("doi:10.1038/nature14539") == "10.1038/nature14539"
        assert normalize_doi("10.1038/NATURE14539") == "10.1038/nature14539"

    def test_rejects_invalid(self) -> None:
        assert normalize_doi(None) is None
        assert normalize_doi("") is None
        assert normalize_doi("not-a-doi") is None
        assert normalize_doi("10.1038 nature") is None  # has a space


class TestNormalizeTitle:
    def test_case_and_punctuation_insensitive(self) -> None:
        assert normalize_title("Deep Learning: A Review!") == "deep learning a review"
        assert normalize_title("  Deep   Learning  ") == "deep learning"
        assert normalize_title(None) == ""


class TestNormalizeAuthors:
    def test_list_of_strings(self) -> None:
        assert normalize_authors(["Smith, J.", "Lee, K."]) == ["Smith, J.", "Lee, K."]

    def test_comma_and_semicolon_split(self) -> None:
        # Documented behaviour: a bare string is split on both ``;`` and ``,``.
        assert normalize_authors("Smith, J.; Lee, K.") == ["Smith", "J.", "Lee", "K."]
        assert normalize_authors("Smith; Lee") == ["Smith", "Lee"]

    def test_dict_authors(self) -> None:
        raw = [{"name": "Yann LeCun", "affiliation": "NYU"}, {"name": "Yoshua Bengio"}]
        assert normalize_authors(raw) == ["Yann LeCun", "Yoshua Bengio"]

    def test_drops_empty(self) -> None:
        assert normalize_authors(None) == []
        assert normalize_authors(["", None, "  ", "Smith"]) == ["Smith"]


class TestCoerceSourceType:
    def test_known_types(self) -> None:
        assert coerce_source_type("journal-article") is SourceType.JOURNAL_ARTICLE
        assert coerce_source_type("proceedings-article") is SourceType.CONFERENCE_PAPER
        assert coerce_source_type("posted-content") is SourceType.PREPRINT

    def test_unknown_defaults_to_other(self) -> None:
        assert coerce_source_type("something-new") is SourceType.OTHER
        assert coerce_source_type(None) is SourceType.OTHER


class TestCoerceYear:
    def test_int_passthrough(self) -> None:
        assert coerce_year(2015) == 2015

    def test_iso_date(self) -> None:
        assert coerce_year("2015-05-26") == 2015

    def test_invalid(self) -> None:
        assert coerce_year(None) is None
        assert coerce_year("") is None
        assert coerce_year("not a year") is None


class TestSourceFromDict:
    def test_maps_known_fields(self) -> None:
        source = source_from_dict(
            {
                "title": "Deep Learning",
                "authors": ["LeCun, Y.", "Bengio, Y."],
                "year": 2015,
                "source": "Nature",
                "doi": "https://doi.org/10.1038/nature14539",
                "article_url": "https://example.org/x",
                "abstract": "an abstract",
                "type": "journal-article",
                "cites": 84128,
            },
            origin="publish_or_perish",
        )
        assert isinstance(source, Source)
        assert source.title == "Deep Learning"
        assert source.authors == ["LeCun, Y.", "Bengio, Y."]
        assert source.year == 2015
        assert source.venue == "Nature"
        assert source.doi == "10.1038/nature14539"
        assert source.url == "https://example.org/x"
        assert source.abstract == "an abstract"
        assert source.source_type is SourceType.JOURNAL_ARTICLE
        assert source.citation_count == 84128
        assert source.provenance is not None
        assert source.provenance.origin == "publish_or_perish"

    def test_preserves_unknown_fields_in_metadata(self) -> None:
        source = source_from_dict(
            {"title": "X", "rank": 3, "publisher": "Nature", "issn": "0028-0836"},
            origin="publish_or_perish",
        )
        assert source.metadata["rank"] == 3
        assert source.metadata["publisher"] == "Nature"
        assert source.metadata["issn"] == "0028-0836"

    def test_missing_fields_are_not_invented(self) -> None:
        source = source_from_dict({"title": "Only title"}, origin="crossref")
        assert source.authors == []
        assert source.year is None
        assert source.doi is None
        assert source.venue is None

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(TypeError):
            source_from_dict("not a dict", origin="crossref")  # type: ignore[arg-type]
