"""Unit tests for source deduplication (pure, no I/O)."""

from __future__ import annotations

from src.schemas.source import Source, SourceType
from src.tools.dedupe import dedupe_key, deduplicate


def _source(
    *,
    title: str,
    doi: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    abstract: str | None = None,
    source_type: SourceType = SourceType.OTHER,
) -> Source:
    return Source(
        title=title,
        doi=doi,
        authors=authors or [],
        year=year,
        abstract=abstract,
        source_type=source_type,
    )


class TestDedupeKey:
    def test_doi_preferred(self) -> None:
        s = _source(title="Deep Learning", doi="https://doi.org/10.1038/nature14539")
        assert dedupe_key(s) == "doi:10.1038/nature14539"

    def test_title_fallback(self) -> None:
        s = _source(title="Deep Learning: A Review!", authors=["Smith, J."], year=2020)
        assert dedupe_key(s) == "title:deep learning a review|smith, j.|2020"

    def test_no_author_no_year(self) -> None:
        s = _source(title="Deep Learning")
        assert dedupe_key(s) == "title:deep learning||"


class TestDeduplicate:
    def test_dedup_by_doi_keeps_most_complete(self) -> None:
        a = _source(title="Deep Learning", doi="10.1038/nature14539", abstract=None)
        b = _source(title="Deep Learning", doi="https://doi.org/10.1038/nature14539", abstract="full abstract")
        result = deduplicate([a, b])
        assert len(result) == 1
        assert result[0].abstract == "full abstract"

    def test_dedup_by_title_author_year(self) -> None:
        a = _source(title="Deep Learning: A Review!", authors=["Smith, J."], year=2020)
        b = _source(title="Deep Learning A Review", authors=["Smith, J."], year=2020)
        result = deduplicate([a, b])
        assert len(result) == 1

    def test_distinct_sources_not_merged(self) -> None:
        a = _source(title="Alpha", year=2020)
        b = _source(title="Beta", year=2021)
        result = deduplicate([a, b])
        assert len(result) == 2

    def test_preserves_first_seen_order(self) -> None:
        a = _source(title="Alpha")
        b = _source(title="Beta")
        c = _source(title="Alpha")  # duplicate of a
        result = deduplicate([a, b, c])
        assert [r.title for r in result] == ["Alpha", "Beta"]

    def test_merge_preserves_metadata(self) -> None:
        a = _source(title="X", doi="10.1/x", abstract=None)
        a.metadata["rank"] = 1
        b = _source(title="X", doi="10.1/x", abstract=None)
        b.metadata["issn"] = "0028-0836"
        result = deduplicate([a, b])
        assert len(result) == 1
        assert result[0].metadata["rank"] == 1
        assert result[0].metadata["issn"] == "0028-0836"
