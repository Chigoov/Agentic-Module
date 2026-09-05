"""Deterministic APA7 reference and in-text citation formatting.

Specification anchors:
  * SYSTEM_RULES.md §E.32 — never invent references during writing.
  * SYSTEM_RULES.md §E.34 — never invent page numbers.
  * AGENT_CONSTITUTION.md §3 — never invent bibliographic metadata.
  * AGENT_CONSTITUTION.md §9 — never invent page numbers or locations.

This module is *pure logic*: it takes a :class:`~src.schemas.source.Source`
that has already been verified and formats it. It never guesses a missing
value — a field that is absent becomes an explicit ``[missing: <field>]`` marker
and is recorded in :attr:`ReferenceEntry.missing_fields` so a later audit can
distinguish a complete reference from a gapped one.
"""

from __future__ import annotations

import re

from src.schemas.citation import (
    CitationStyle,
    InTextCitation,
    ReferenceEntry,
    ReferenceList,
)
from src.schemas.source import Source

__all__ = [
    "citation_key_for",
    "format_reference",
    "format_reference_list",
    "build_in_text_citation",
    "format_in_text_author_year",
]

_UNSUPPORTED = re.compile(r"[^a-z0-9]+")
_UNDATED = "n.d."


def _surname(author: str) -> str:
    """Extract a surname from a normalized author string (``"Smith, J."``)."""
    cleaned = (author or "").strip()
    if not cleaned:
        return ""
    if "," in cleaned:
        return cleaned.split(",", 1)[0].strip()
    # Fallback: last whitespace-separated token is the surname.
    return cleaned.split()[-1].strip()


def _title_slug(title: str) -> str:
    """A stable, lowercase key fragment derived from the first significant word."""
    words = _UNSUPPORTED.split((title or "").lower())
    significant = [w for w in words if w]
    return significant[0] if significant else "untitled"


def citation_key_for(source: Source) -> str:
    """Derive a stable machine citation key (e.g. ``smith2012``).

    The key is built *only* from fields that exist on the source. When the author
    or year is missing, a deterministic fallback is used instead of a guess.
    """
    surname = _surname(source.authors[0]) if source.authors else ""
    if surname:
        stem = _UNSUPPORTED.sub("", surname.lower())
    else:
        stem = _title_slug(source.title)
    year = str(source.year) if source.year is not None else _UNDATED
    return f"{stem}{year}"


def format_in_text_author_year(source: Source) -> str:
    """Human-facing author-year form, only from fields that exist on the source.

    * 1 author → ``"Smith, 2012"``
    * 2 authors → ``"Smith & Lee, 2012"``
    * 3+ authors → ``"Smith et al., 2012"``
    * no authors → ``"Title, 2012"``
    * no year → ``"n.d."``
    """
    year = str(source.year) if source.year is not None else _UNDATED
    if not source.authors:
        return f"{_title_slug(source.title).title()}, {year}"
    if len(source.authors) == 1:
        return f"{_surname(source.authors[0]).title()}, {year}"
    if len(source.authors) == 2:
        first = _surname(source.authors[0]).title()
        second = _surname(source.authors[1]).title()
        return f"{first} & {second}, {year}"
    first = _surname(source.authors[0]).title()
    return f"{first} et al., {year}"


def _format_authors(authors: list[str]) -> tuple[str, list[str]]:
    """Format the author list for a reference entry (APA7, up to 20 authors).

    Returns the rendered author string and the list of missing-field markers.
    """
    missing: list[str] = []
    if not authors:
        return "[missing: author]", ["author"]

    # APA7 lists up to 20 authors; beyond that, ellipsis + final author.
    if len(authors) <= 20:
        listed = authors
    else:
        listed = authors[:19] + ["…"] + [authors[-1]]

    if len(listed) == 1:
        return listed[0], missing
    head = ", ".join(listed[:-1])
    return f"{head}, & {listed[-1]}", missing


def format_reference(source: Source, style: CitationStyle = CitationStyle.APA7) -> ReferenceEntry:
    """Format one verified :class:`Source` into an APA7 reference entry.

    Missing fields become explicit ``[missing: <field>]`` markers and are recorded
    in ``missing_fields``. Values are never invented.
    """
    if style is not CitationStyle.APA7:
        # Future styles extend CitationStyle; refuse rather than silently misformat.
        raise ValueError(f"Unsupported citation style: {style}")

    missing: list[str] = []
    authors_str, author_missing = _format_authors(source.authors)
    missing.extend(author_missing)

    year_str = str(source.year) if source.year is not None else _UNDATED
    if source.year is None:
        missing.append("year")

    if source.title:
        title_str = source.title
    else:
        title_str = "[missing: title]"
        missing.append("title")

    if source.venue:
        venue_str = source.venue
    else:
        venue_str = "[missing: venue]"
        missing.append("venue")

    if source.doi:
        locator = f"https://doi.org/{source.doi}"
    elif source.url:
        locator = source.url
    else:
        locator = "[missing: doi/url]"
        missing.append("doi/url")

    formatted = f"{authors_str} ({year_str}). {title_str}. {venue_str}. {locator}"
    return ReferenceEntry(
        citation_key=citation_key_for(source),
        source_id=source.id,
        formatted=formatted,
        missing_fields=missing,
    )


def format_reference_list(
    sources: list[Source],
    style: CitationStyle = CitationStyle.APA7,
    *,
    project_id: str | None = None,
) -> ReferenceList:
    """Format a list of verified sources into an ordered :class:`ReferenceList`."""
    entries = [format_reference(source, style) for source in sources]
    return ReferenceList(project_id=project_id, style=style, entries=entries)


def build_in_text_citation(
    source: Source,
    style: CitationStyle = CitationStyle.APA7,
    *,
    locator: str | None = None,
    verbatim: bool = False,
) -> InTextCitation:
    """Build an in-text citation pointer for a verified source.

    ``locator`` must be supplied by the caller from real retrieved content; it is
    never synthesized here.
    """
    if style is not CitationStyle.APA7:
        raise ValueError(f"Unsupported citation style: {style}")
    return InTextCitation(
        citation_key=citation_key_for(source),
        source_id=source.id,
        author_year_form=format_in_text_author_year(source),
        locator=locator,
        verbatim=verbatim,
    )
