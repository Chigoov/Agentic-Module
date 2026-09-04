"""Source deduplication.

Specification anchors:
  * SYSTEM_RULES.md §D — discovery produces candidates; duplicates must not
    inflate the candidate list or the citation count.
  * AGENT_CONSTITUTION.md §1–§5 — a source's identity must not be fabricated;
    dedup keys are derived only from real, present fields.

Deduplication is deterministic and pure. A source is keyed by its normalized DOI
when one is present; otherwise it falls back to a normalized ``title + first
author + year`` key. Records that match on the stronger key are merged, keeping
the most complete record and recording the merge in ``verification_notes``.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.schemas.source import Source, SourceType
from src.tools.source_mapper import normalize_doi, normalize_title

__all__ = ["dedupe_key", "deduplicate"]


def dedupe_key(source: Source) -> str:
    """Return a stable comparison key for a source.

    DOI (normalized) is preferred as the strongest identity. When absent, the key
    falls back to ``title | first-author | year`` using the normalized title so
    punctuation/case differences do not split the same work.
    """
    doi = normalize_doi(source.doi)
    if doi:
        return f"doi:{doi}"

    title = normalize_title(source.title)
    first_author = source.authors[0].strip().lower() if source.authors else ""
    year = source.year if source.year is not None else ""
    return f"title:{title}|{first_author}|{year}"


def _completeness(source: Source) -> int:
    """Score how complete a record is, to pick the best representative on merge."""
    score = 0
    if source.doi:
        score += 4
    if source.abstract:
        score += 3
    if source.venue:
        score += 2
    if source.citation_count is not None:
        score += 1
    if source.url:
        score += 1
    if source.authors:
        score += 1
    return score


def _merge(preferred: Source, other: Source) -> Source:
    """Merge ``other`` into ``preferred`` in place, filling gaps and preserving data.

    Never drops data: fields absent on the preferred record are backfilled from
    ``other``, and any metadata keys unique to ``other`` are merged into
    ``preferred.metadata``.
    """
    preferred.authors = preferred.authors or other.authors
    preferred.year = preferred.year if preferred.year is not None else other.year
    preferred.venue = preferred.venue or other.venue
    preferred.doi = preferred.doi or other.doi
    preferred.url = preferred.url or other.url
    preferred.abstract = preferred.abstract or other.abstract
    if preferred.citation_count is None and other.citation_count is not None:
        preferred.citation_count = other.citation_count
    if preferred.source_type == SourceType.OTHER and other.source_type != SourceType.OTHER:
        preferred.source_type = other.source_type

    for key, value in other.metadata.items():
        if key not in preferred.metadata:
            preferred.metadata[key] = value

    preferred.add_verification_note(f"Deduplicated: merged with {other.id}")
    preferred.touch()
    return preferred


def deduplicate(sources: Iterable[Source]) -> list[Source]:
    """Return a deduplicated list, keeping the most complete record per key.

    Preserves first-seen order. Sources with an identical DOI key are merged
    first; the fallback title/author/year key catches works that share a title
    but whose DOI is missing on one side.
    """
    by_key: dict[str, Source] = {}
    order: list[str] = []

    for source in sources:
        key = dedupe_key(source)
        if key in by_key:
            existing = by_key[key]
            # Keep the more complete record as the representative.
            if _completeness(source) > _completeness(existing):
                _merge(source, existing)
                by_key[key] = source
            else:
                _merge(existing, source)
        else:
            by_key[key] = source
            order.append(key)

    return [by_key[key] for key in order]
