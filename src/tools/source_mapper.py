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
from src.schemas.source import AccessMode, RightsStatus, Source, SourceType

__all__ = [
    "normalize_doi",
    "normalize_title",
    "normalize_authors",
    "coerce_source_type",
    "coerce_year",
    "source_from_dict",
    "best_title_match",
    "classify_rights_and_access",
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


def classify_rights_and_access(
    *,
    download_urls: list[str] | None = None,
    landing_url: str | None = None,
    license_text: str | None = None,
    rights_status_hint: RightsStatus | str | None = None,
    access_mode_hint: AccessMode | str | None = None,
    ebook_access: str | None = None,
    is_preview: bool = False,
) -> tuple[RightsStatus, AccessMode]:
    """Deterministically classify rights_status and access_mode.

    Rules:
    - Never infer OPEN_DOWNLOAD from .pdf extension alone.
    - BORROW_ONLY and PREVIEW_ONLY must never become OPEN_DOWNLOAD.
    - If license or access is unclear -> (UNKNOWN, UNKNOWN).
    - OPEN_DOWNLOAD requires verified download URL + clear open rights.
    """
    rights = RightsStatus.UNKNOWN
    if isinstance(rights_status_hint, RightsStatus):
        rights = rights_status_hint
    elif isinstance(rights_status_hint, str):
        try:
            rights = RightsStatus(rights_status_hint)
        except ValueError:
            rights = RightsStatus.UNKNOWN

    if rights is RightsStatus.UNKNOWN and license_text:
        if isinstance(license_text, list):
            parts = []
            for item in license_text:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if v)
                elif item is not None:
                    parts.append(str(item))
            lt = " ".join(parts).lower()
        elif isinstance(license_text, dict):
            lt = " ".join(str(v) for v in license_text.values() if v).lower()
        else:
            lt = str(license_text).lower()

        if any(term in lt for term in ("public domain", "cc0", "cc-0", "zero")):
            rights = RightsStatus.PUBLIC_DOMAIN
        elif any(term in lt for term in ("creative commons", "cc by", "cc-by", "open access", "open license", "gpl", "mit license", "apache")):
            rights = RightsStatus.OPEN_LICENSE
        elif any(term in lt for term in ("free to read", "free download", "free access", "freely available")):
            rights = RightsStatus.PROVIDER_STATED_FREE
        elif any(term in lt for term in ("all rights reserved", "restricted", "copyright", "proprietary", "borrow", "subscription", "paywall")):
            rights = RightsStatus.RESTRICTED

    access = AccessMode.UNKNOWN
    if isinstance(access_mode_hint, AccessMode):
        access = access_mode_hint
    elif isinstance(access_mode_hint, str):
        try:
            access = AccessMode(access_mode_hint)
        except ValueError:
            access = AccessMode.UNKNOWN

    ea = (ebook_access or "").lower()
    if ea in {"borrowable", "borrow", "inlibrary"}:
        access = AccessMode.BORROW_ONLY
        if rights is RightsStatus.UNKNOWN:
            rights = RightsStatus.RESTRICTED
    elif ea in {"preview", "preview_only"} or is_preview:
        access = AccessMode.PREVIEW_ONLY
    elif access is AccessMode.UNKNOWN:
        has_downloads = bool(download_urls and any(u.strip() for u in download_urls))
        is_open_rights = rights in {
            RightsStatus.PUBLIC_DOMAIN,
            RightsStatus.OPEN_LICENSE,
            RightsStatus.PROVIDER_STATED_FREE,
        }
        if has_downloads and is_open_rights and not is_preview:
            access = AccessMode.OPEN_DOWNLOAD
        elif is_open_rights and (landing_url or has_downloads):
            access = AccessMode.READ_ONLINE
        elif rights is RightsStatus.RESTRICTED:
            access = AccessMode.UNKNOWN

    return rights, access


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
        "publisher",
        "isbn",
        "language",
        "landing_url",
        "download_urls",
        "license",
        "license_url",
        "rights_status",
        "access_mode",
        "provider",
        "provider_record_id",
        "ebook_access",
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

    # Preserve publisher in metadata if explicitly passed (backward compatibility)
    if "publisher" in data:
        metadata["publisher"] = data["publisher"]

    publisher = data.get("publisher")
    venue = data.get("venue") or data.get("source") or publisher
    isbn = data.get("isbn")
    language = data.get("language")
    landing_url = data.get("landing_url") or data.get("url") or data.get("article_url")
    url = data.get("url") or data.get("article_url") or landing_url

    raw_dl = data.get("download_urls")
    download_urls: list[str] = []
    if isinstance(raw_dl, list):
        download_urls = [str(u) for u in raw_dl if u]
    elif isinstance(raw_dl, str) and raw_dl.strip():
        download_urls = [raw_dl.strip()]

    raw_license = data.get("license")
    license_url = data.get("license_url")
    license_text: str | None = None
    if isinstance(raw_license, list):
        parts = []
        for item in raw_license:
            if isinstance(item, dict):
                if not license_url and item.get("URL"):
                    license_url = str(item["URL"])
                parts.extend(str(v) for v in item.values() if v)
            elif item is not None:
                parts.append(str(item))
        license_text = ", ".join(parts) if parts else None
    elif isinstance(raw_license, dict):
        if not license_url and raw_license.get("URL"):
            license_url = str(raw_license["URL"])
        license_text = ", ".join(f"{k}: {v}" for k, v in raw_license.items())
    elif raw_license is not None:
        license_text = str(raw_license)

    provider = data.get("provider") or origin
    provider_record_id = data.get("provider_record_id")

    rights_status, access_mode = classify_rights_and_access(
        download_urls=download_urls,
        landing_url=landing_url,
        license_text=license_text,
        rights_status_hint=data.get("rights_status"),
        access_mode_hint=data.get("access_mode"),
        ebook_access=data.get("ebook_access"),
    )

    source = Source(
        title=data.get("title") or "",
        authors=authors,
        year=coerce_year(data.get("year")),
        venue=venue,
        doi=doi,
        url=url,
        abstract=data.get("abstract"),
        source_type=source_type,
        citation_count=citation_count,
        metadata=metadata,
        publisher=publisher,
        isbn=isbn,
        language=language,
        landing_url=landing_url,
        download_urls=download_urls,
        license=license_text,
        license_url=license_url,
        rights_status=rights_status,
        access_mode=access_mode,
        provider=provider,
        provider_record_id=provider_record_id,
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
