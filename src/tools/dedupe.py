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

import re
from collections.abc import Iterable

from src.schemas.source import Source, SourceType
from src.tools.source_mapper import normalize_doi, normalize_title

__all__ = ["dedupe_key", "deduplicate"]


def dedupe_key(source: Source) -> str:
    """Return a stable comparison key for a source.

    Deduplication is deterministic:
    1. DOI (normalized) is preferred as the strongest identity.
    2. ISBN (clean 10/13 digits) is second for books without DOI.
    3. Provider ID (provider + record ID) is third.
    4. Fallback is normalized title | first-author | year.
    """
    doi = normalize_doi(source.doi)
    if doi:
        return f"doi:{doi}"

    isbn = _isbn(source)
    if isbn:
        return f"isbn:{isbn}"

    prov = getattr(source, "provider", None)
    prov_id = getattr(source, "provider_record_id", None)
    if prov and prov_id:
        return f"provider:{prov}:{prov_id}"

    title = normalize_title(source.title)
    first_author = source.authors[0].strip().lower() if source.authors else ""
    year = source.year if source.year is not None else ""
    return f"title:{title}|{first_author}|{year}"


def _isbn(source: Source) -> str | None:
    value = re.sub(r"[^0-9X]", "", (source.isbn or "").upper())
    return value if len(value) in {10, 13} else None


def _bibliographic_key(source: Source) -> tuple:
    return (normalize_title(source.title), tuple(a.casefold().strip() for a in source.authors), source.year)


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
    preferred.isbn = preferred.isbn or other.isbn
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


def deduplicate(sources: Iterable[Source], *, identities: dict[str, str | None] | None = None) -> list[Source]:
    """Merge unambiguous aliases and optionally map input IDs to publication identities.

    A missing identifier that matches conflicting identities maps to None.
    Conflicting DOI/ISBN identities remain separate, including when a record
    without an identifier arrives before both identified records.
    """
    records = list(sources)
    by_key: dict[str, list[int]] = {}
    by_title: dict[tuple, list[int]] = {}
    strong: dict[tuple, tuple[set, set]] = {}
    for source in records:
        dois, isbns = strong.setdefault(_bibliographic_key(source), (set(), set()))
        if source.doi:
            dois.add(normalize_doi(source.doi))
        if _isbn(source):
            isbns.add(_isbn(source))
    result: list[Source] = []
    input_indexes = {}
    for source in records:
        key, secondary = dedupe_key(source), _bibliographic_key(source)
        candidates = by_key.get(key, [])
        if not candidates and all(secondary):
            candidates = by_title.get(secondary, [])
        matches = [i for i in candidates if not (
            source.doi and result[i].doi and normalize_doi(source.doi) != normalize_doi(result[i].doi)
            or _isbn(source) and _isbn(result[i]) and _isbn(source) != _isbn(result[i])
            or len(strong[secondary][0]) > 1 and normalize_doi(source.doi) != normalize_doi(result[i].doi)
            or len(strong[secondary][1]) > 1 and _isbn(source) != _isbn(result[i]))]
        index = matches[0] if len(matches) == 1 else None
        if index is None:
            index = len(result)
            result.append(source)
            by_title.setdefault(secondary, []).append(index)
        else:
            existing = result[index]
            if _completeness(source) > _completeness(existing):
                result[index] = _merge(source, existing)
            else:
                _merge(existing, source)
        for alias_key in (key, dedupe_key(result[index])):
            indexes = by_key.setdefault(alias_key, [])
            if index not in indexes:
                indexes.append(index)
        input_indexes[source.id] = index
    if identities is not None:
        for source in records:
            representative = result[input_indexes[source.id]]
            dois, isbns = strong[_bibliographic_key(source)]
            ambiguous = len(dois) > 1 and not representative.doi or len(isbns) > 1 and not _isbn(representative)
            identities[source.id] = None if ambiguous else (
                dedupe_key(representative) if representative.doi or _isbn(representative) else representative.id)
    return result
