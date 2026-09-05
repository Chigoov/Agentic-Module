"""Citation and reference-list schemas.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §21 — citation audit requirements.
  * SYSTEM_RULES.md §E.31/§E.32 — never invent references during writing.
  * AGENT_CONSTITUTION.md §3/§9 — never invent metadata or page numbers.

Citations are split into two concerns: an :class:`InTextCitation` (the author-year
pointer inside prose) and a :class:`ReferenceEntry` (the formatted bibliography
item). Keeping them separate means an audit can check that every in-text pointer
resolves to a real entry, and every entry resolves to a real verified source.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from src.schemas.base import BaseRecord, SchemaModel

__all__ = [
    "CitationStyle",
    "InTextCitation",
    "ReferenceEntry",
    "ReferenceList",
]


class CitationStyle(StrEnum):
    """Supported bibliographic styles. Extensible without contract changes."""

    APA7 = "APA7"


class InTextCitation(SchemaModel):
    """An author-year pointer placed inside the draft prose.

    ``citation_key`` is the stable machine key (e.g. ``smith2012``) that links the
    pointer to a :class:`ReferenceEntry`; ``author_year_form`` is the human-facing
    rendering produced only from fields that actually exist on the source.
    """

    citation_key: str
    source_id: str
    author_year_form: str
    #: Optional locator, e.g. ``"p. 42"``. Never invented (AGENT_CONSTITUTION §9).
    locator: str | None = None
    #: Whether the citation accompanies a verbatim quotation.
    verbatim: bool = False


class ReferenceEntry(SchemaModel):
    """A single formatted bibliography item.

    ``missing_fields`` records which bibliographic fields were absent so that a
    later audit can distinguish "formatted completely" from "formatted with gaps"
    — the formatter never guesses a missing value.
    """

    citation_key: str
    source_id: str
    formatted: str
    missing_fields: list[str] = Field(default_factory=list)


class ReferenceList(BaseRecord):
    """The ordered bibliography for a project.

    ``project_id`` ties the list back to the project it belongs to; ``entries``
    are the formatted items, one per cited source.
    """

    id_prefix: str = Field(default="ref", exclude=True, repr=False)

    project_id: str | None = None
    style: CitationStyle = CitationStyle.APA7
    entries: list[ReferenceEntry] = Field(default_factory=list)
