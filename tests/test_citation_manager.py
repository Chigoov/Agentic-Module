"""Fast, network-free tests for the citation manager (Phase 6)."""

from __future__ import annotations

from src.schemas.source import Source
from src.tools.citation_manager import CitationManager, detect_orphan_citations


def _source(*, title: str, authors: list[str], year: int) -> Source:
    return Source(title=title, authors=authors, year=year)


def test_register_source_returns_key() -> None:
    manager = CitationManager()
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    key = manager.register_source(source)
    assert key == "smith2012"


def test_collision_disambiguation() -> None:
    manager = CitationManager()
    first = _source(title="Alpha", authors=["Smith, J."], year=2012)
    second = _source(title="Beta", authors=["Smith, J."], year=2012)
    key_first = manager.register_source(first)
    key_second = manager.register_source(second)
    assert key_first == "smith2012"
    assert key_second == "smith2012a"


def test_resolve_and_cited_sources() -> None:
    manager = CitationManager()
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    key = manager.register_source(source)
    assert manager.resolve(key) is source
    assert manager.cited_sources() == [source]
    assert manager.citation_key_for_source(source.id) == key


def test_detect_orphan_citations() -> None:
    manager = CitationManager()
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    manager.register_source(source)
    text = "Smith (smith2012) argues, while a mystery source (lee2019) does not."
    orphans = manager.detect_orphan_citations(text)
    assert orphans == ["lee2019"]


def test_detect_orphan_no_orphans_when_all_known() -> None:
    manager = CitationManager()
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    manager.register_source(source)
    assert manager.detect_orphan_citations("See smith2012 for details.") == []


def test_module_level_detect_orphan_citations() -> None:
    known = {"smith2012"}
    assert detect_orphan_citations("See smith2012 and lee2019.", known) == ["lee2019"]
