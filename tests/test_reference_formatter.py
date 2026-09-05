"""Fast, network-free tests for the APA7 reference formatter (Phase 6)."""

from __future__ import annotations

import pytest

from src.schemas.citation import CitationStyle
from src.schemas.source import Source, SourceType
from src.tools.reference_formatter import (
    citation_key_for,
    format_in_text_author_year,
    format_reference,
    format_reference_list,
)


def _source(**overrides: object) -> Source:
    fields: dict[str, object] = {
        "title": "Attention is all you need",
        "authors": ["Vaswani, A.", "Shazeer, N."],
        "year": 2017,
        "venue": "Advances in Neural Information Processing Systems",
        "doi": "10.48550/arXiv.1706.03762",
        "source_type": SourceType.CONFERENCE_PAPER,
    }
    fields.update(overrides)
    return Source(**fields)


# --------------------------------------------------------------------------- #
# citation_key_for
# --------------------------------------------------------------------------- #
def test_citation_key_from_author_year() -> None:
    assert citation_key_for(_source()) == "vaswani2017"


def test_citation_key_falls_back_to_title_when_no_author() -> None:
    source = _source(authors=[])
    assert citation_key_for(source) == "attention2017"


def test_citation_key_undated_when_no_year() -> None:
    source = _source(year=None)
    assert citation_key_for(source) == "vaswanin.d."


def test_citation_key_single_author() -> None:
    source = _source(authors=["Smith, J."], title="On the origin of species")
    assert citation_key_for(source) == "smith2017"


# --------------------------------------------------------------------------- #
# format_in_text_author_year
# --------------------------------------------------------------------------- #
def test_in_text_single_author() -> None:
    source = _source(authors=["Smith, J."])
    assert format_in_text_author_year(source) == "Smith, 2017"


def test_in_text_two_authors() -> None:
    source = _source(authors=["Smith, J.", "Lee, K."])
    assert format_in_text_author_year(source) == "Smith & Lee, 2017"


def test_in_text_three_plus_authors() -> None:
    source = _source(authors=["Smith, J.", "Lee, K.", "Kim, P."])
    assert format_in_text_author_year(source) == "Smith et al., 2017"


def test_in_text_no_year_uses_nd() -> None:
    source = _source(year=None)
    assert format_in_text_author_year(source) == "Vaswani & Shazeer, n.d."


# --------------------------------------------------------------------------- #
# format_reference
# --------------------------------------------------------------------------- #
def test_format_reference_complete() -> None:
    entry = format_reference(_source())
    assert entry.citation_key == "vaswani2017"
    assert "Vaswani, A., & Shazeer, N. (2017)" in entry.formatted
    assert "Attention is all you need" in entry.formatted
    assert "https://doi.org/10.48550/arXiv.1706.03762" in entry.formatted
    assert entry.missing_fields == []


def test_format_reference_marks_missing_fields() -> None:
    source = _source(authors=[], year=None, venue=None, doi=None, url=None, title="")
    entry = format_reference(source)
    assert "author" in entry.missing_fields
    assert "year" in entry.missing_fields
    assert "[missing: author]" in entry.formatted


def test_format_reference_never_invents() -> None:
    source = _source(year=None, doi=None, url=None)
    entry = format_reference(source)
    assert "n.d." in entry.formatted
    assert "[missing: doi/url]" in entry.formatted
    assert entry.missing_fields


def test_format_reference_rejects_unknown_style() -> None:
    with pytest.raises(ValueError):
        format_reference(_source(), style="MLA")


# --------------------------------------------------------------------------- #
# format_reference_list
# --------------------------------------------------------------------------- #
def test_format_reference_list_orders_and_projects() -> None:
    sources = [_source(authors=["Smith, J."]), _source(authors=["Lee, K."])]
    reference_list = format_reference_list(sources, project_id="prj_1")
    assert reference_list.project_id == "prj_1"
    assert reference_list.style is CitationStyle.APA7
    assert [e.source_id for e in reference_list.entries] == [s.id for s in sources]
