"""Provider → Source normalization and mapping layer.

Specification anchors:
  * ARCHITECTURE.md §8 — every important object has a stable schema.
  * AGENT_CONSTITUTION.md §1–§5 — source integrity; never invent fields.
  * SYSTEM_RULES.md §H.50 — preserve raw external results for auditability.
  * PHASE 3 EXECUTION ADDENDUM §7 — preserve unknown response fields in
    ``Source.metadata`` rather than silently discarding them.

This module is a pure, deterministic boundary between provider payloads and the
internal :class:`~src.schemas.source.Source` contract. It never performs I/O and
never guesses a value that was absent from the input. Fields a provider returns
that do not map onto a ``Source`` field are preserved verbatim in ``metadata``.

This is the component that resolves the audit finding A2 (the Publish-or-Perish
``_normalize()`` output did not match the ``Source`` schema): ``to_sources()`` on
the adapter now routes through :func:`source_from_dict` so the result is a real
``list[Source]`` instead of a list of ad-hoc dicts.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from src.schemas.base import Provenance
from src.schemas.source import Source, SourceType

__all__ = [
    "normalize_doi",
    "normalize_title",
    "normalize_authors",
    "coerce_source_type",
    "coerce_year",
    "source_from_dict",
    "best_title_match",
]

#: DOI prefix forms that are stripped before comparison/storage.
_DOI_PREFIXES: tuple[str, ...] = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)

#: Characters removed when normalizing a title into a dedup/compare key.
_TITLE_PUNCTUATION = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

#: Provider ``type`` / ``source_type`` strings → :class:`SourceType`.
_TYPE_MAP: dict[str, SourceType] = {
    "journal-article": SourceType.JOURNAL_ARTICLE,
    "journal_article": SourceType.JOURNAL_ARTICLE,
    "article": SourceType.JOURNAL_ARTICLE,
    "proceedings-article": SourceType.CONFERENCE_PAPER,
    "proceedings_article": SourceType.CONFERENCE_PAPER,
    "conference-paper": SourceType.CONFERENCE_PAPER,
    "conference_paper": SourceType.CONFERENCE_PAPER,
    "book": SourceType.BOOK,
    "book-chapter": SourceType.BOOK_CHAPTER,
    "book_chapter": SourceType.BOOK_CHAPTER,
    "chapter": SourceType.BOOK_CHAPTER,
    "dissertation": SourceType.THESIS,
    "thesis": SourceType.THESIS,
    "posted-content": SourceType.PREPRINT,
    "preprint": SourceType.PREPRINT,
    "report": SourceType.TECHNICAL_REPORT,
    "technical-report": SourceType.TECHNICAL_REPORT,
    "web": SourceType.WEB_RESOURCE,
    "web-resource": SourceType.WEB_RESOURCE,
    "web_resource": SourceType.WEB_RESOURCE,
}


def normalize_doi(value: Any) -> str | None:
    """Normalize a DOI to a bare, lowercase form, or ``None`` when unusable.

    Strips ``https://doi.org/``, ``dx.doi.org``, and the ``doi:`` prefix, then
    lowercases and trims. Returns ``None`` for empty or malformed values rather
    than fabricating a DOI (AGENT_CONSTITUTION.md §2).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
            break
    lowered = lowered.strip()
    # A DOI must contain the "10." registrar prefix; anything else is not one.
    if not lowered.startswith("10.") or " " in lowered:
        return None
    return lowered


def normalize_title(value: Any) -> str:
    """Return a case/punctuation-insensitive title key for comparison/dedup."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = _TITLE_PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def normalize_authors(raw: Any) -> list[str]:
    """Normalize author input into a list of name strings.

    Accepts a single string (split on ``;`` or ``,``), a list of strings, or a
    list of dicts (OpenAlex style ``{"name": ..., "affiliation": ...}``). Empty
    and ``None`` entries are dropped; names are never invented.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        entries: list[Any] = [part for part in re.split(r"[;,]", raw) if part.strip()]
    elif isinstance(raw, list):
        entries = list(raw)
    else:
        # A scalar we don't recognise (unlikely); treat as a single author name.
        entries = [raw]

    names: list[str] = []
    for entry in entries:
        if entry is None:
            continue
        if isinstance(entry, str):
            name = entry.strip()
            if name:
                names.append(name)
        elif isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return names


def coerce_source_type(raw: Any) -> SourceType:
    """Map a provider type string to :class:`SourceType`, defaulting to ``OTHER``."""
    if raw is None:
        return SourceType.OTHER
    if isinstance(raw, SourceType):
        return raw
    key = str(raw).strip().lower().replace(" ", "-")
    return _TYPE_MAP.get(key, SourceType.OTHER)


def coerce_year(raw: Any) -> int | None:
    """Coerce a provider year value to ``int`` or ``None``.

    Handles full dates (e.g. ``"2012-01-15"``) and plain integers. Returns
    ``None`` for missing/unparseable values rather than guessing a year.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    text = str(raw).strip()
    if not text:
        return None
    # Accept a leading 4-digit year (ISO date strings are common from Crossref).
    match = re.match(r"^(\d{4})", text)
    if not match:
        return None
    year = int(match.group(1))
    return year if 0 <= year <= 9999 else None


def source_from_dict(
    data: dict[str, Any],
    *,
    origin: str,
    source_type_hint: SourceType | None = None,
) -> Source:
    """Build a validated :class:`Source` from a provider record dict.

    Recognised fields map onto ``Source``; every remaining field is preserved in
    ``Source.metadata`` (never silently discarded). Missing recognised fields
    stay ``None`` and are never invented.

    Parameters
    ----------
    data:
        Provider record (e.g. one raw Crossref/OpenAlex/PubMed object, or one
        PoP ``_normalize()`` output).
    origin:
        Provenance origin label, e.g. ``"crossref"`` or ``"publish_or_perish"``.
    source_type_hint:
        Optional caller-supplied type, used only when ``data`` carries no type.
    """
    if not isinstance(data, dict):
        raise TypeError(f"source_from_dict expects a dict, got {type(data).__name__}")

    # Keys we map directly onto Source fields. Aliases cover the Publish-or-
    # Perish naming (``source`` → venue, ``article_url`` → url, ``cites`` →
    # citation_count) plus the canonical names.
    known_keys = {
        "title",
        "authors",
        "year",
        "venue",
        "source",
        "doi",
        "url",
        "article_url",
        "abstract",
        "source_type",
        "type",
        "citation_count",
        "cited_by",
        "cites",
    }

    authors = normalize_authors(data.get("authors"))

    # Determine the type: explicit provider type, else the hint, else OTHER.
    provider_type = data.get("source_type") or data.get("type")
    if provider_type is not None:
        source_type = coerce_source_type(provider_type)
    elif source_type_hint is not None:
        source_type = source_type_hint
    else:
        source_type = SourceType.OTHER

    doi = normalize_doi(data.get("doi"))

    citation_count = _coerce_int(
        data.get("citation_count", data.get("cited_by", data.get("cites")))
    )

    metadata: dict[str, Any] = {}
    for key, value in data.items():
        if key in known_keys:
            continue
        metadata[key] = value

    source = Source(
        title=data.get("title") or "",
        authors=authors,
        year=coerce_year(data.get("year")),
        venue=data.get("venue") or data.get("source"),
        doi=doi,
        url=data.get("url") or data.get("article_url"),
        abstract=data.get("abstract"),
        source_type=source_type,
        citation_count=citation_count,
        metadata=metadata,
    )

    if origin:
        source.provenance = Provenance(origin=origin)

    return source


def _coerce_int(value: Any) -> int | None:
    """Coerce a numeric value to ``int`` or ``None`` without raising."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _tokenize(text: str) -> set[str]:
    return set(_WHITESPACE.split(normalize_title(text)))


def best_title_match(candidate: str, candidates: Iterable[str]) -> tuple[str | None, float]:
    """Return the best-matching title and its Jaccard similarity in ``[0.0, 1.0]``.

    Deterministic and network-free. Used by the verification engine to decide
    which provider record corroborates a candidate source's title. A returned
    ratio of ``1.0`` means exact token equality after normalization; ``None`` is
    returned (with ``0.0``) when there are no candidates.
    """
    if not candidate:
        return None, 0.0
    needle = _tokenize(candidate)
    if not needle:
        return None, 0.0

    best_title: str | None = None
    best_score = 0.0
    for title in candidates:
        if title is None:
            continue
        tokens = _tokenize(str(title))
        if not tokens:
            continue
        intersection = len(needle & tokens)
        union = len(needle | tokens)
        score = intersection / union if union else 0.0
        if score > best_score:
            best_score = score
            best_title = str(title)
    return best_title, best_score
