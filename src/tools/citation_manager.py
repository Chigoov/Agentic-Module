"""Deterministic citation manager.

Specification anchors:
  * SYSTEM_RULES.md §E.32 — never invent references during writing.
  * SYSTEM_RULES.md §E.39 — every citation must map to a source.
  * AGENT_CONSTITUTION.md §4 — never cite an unverified source.

The manager keeps a one-to-one mapping from a stable ``citation_key`` to a
verified :class:`~src.schemas.source.Source`. Keys are derived deterministically
and disambiguated on collision so two same-surname/same-year works never map to
the same key. ``detect_orphan_citations`` scans draft text for citation keys that
have no registered source, closing the loop that prevents fabricated references.
"""

from __future__ import annotations

import re

from src.schemas.source import Source
from src.tools.reference_formatter import citation_key_for, format_in_text_author_year

__all__ = [
    "CitationManager",
    "CITATION_KEY_PATTERN",
    "INTERNAL_TOKEN_PATTERN",
    "AUTHOR_YEAR_CITATION_PATTERN",
    "detect_orphan_citations",
    "detect_internal_tokens",
    "detect_orphan_author_year_citations",
    "known_author_year_forms",
]

#: Matches a machine citation key such as ``smith2012`` or ``smith2012a``.
#: The lookbehind also excludes ``/`` so DOI/URL path segments such as
#: ``.../nature14539`` are never misread as citation keys (found in CLI testing).
CITATION_KEY_PATTERN = re.compile(r"(?<![a-zA-Z0-9/])([a-z][a-z0-9]*[0-9]{4}[a-z]?)(?![a-zA-Z0-9])")
#: Internal ChatGPT/file citation tokens that must never survive into output
#: (AGENTS.md rules; audit A02). Matches ``turn...``, ``view...``, ``search...``,
#: ``filecite``/``filecite...``, the CJK citation brackets, and ``citeturn...``.
INTERNAL_TOKEN_PATTERN = re.compile(r"turn\d+|view\d+|search\d+|filecite|[\u3010\u3011]|citeturn")
#: Author-year in-text citation, e.g. ``(Smith, 2012)``, ``(Smith, 2012, p. 42)``
#: or ``(Smith & Lee, 2012)``. The name part must start with a letter so machine
#: keys and ``[missing: ...]`` markers never match.
AUTHOR_YEAR_CITATION_PATTERN = re.compile(
    r"\((?P<name>[A-Za-z][A-Za-z .,'&\u2019-]*?),\s*"
    r"(?P<year>\d{4}|n\.d\.)"
    r"(?P<locator>(?:,\s*(?:p|pp)\.[^()]*)?)\)"
)

_DISAMBIGUATION = "abcdefghijklmnopqrstuvwxyz"


class CitationManager:
    """Registry of cited sources keyed by a stable, collision-free citation key."""

    def __init__(self) -> None:
        self._by_key: dict[str, Source] = {}
        self._by_source_id: dict[str, str] = {}
        self._order: list[str] = []

    # ---------------------------------------------------------------- register
    def register_source(self, source: Source) -> str:
        """Register ``source`` and return its (possibly disambiguated) key.

        Registering a source is what marks it as cited. If the derived key already
        exists for a *different* source, a letter suffix is appended
        (``smith2012`` → ``smith2012b``) rather than overwriting the mapping.
        """
        base = citation_key_for(source)
        key = base
        attempt = 0
        while key in self._by_key and self._by_key[key].id != source.id:
            attempt += 1
            if attempt > len(_DISAMBIGUATION):
                raise RuntimeError(f"Too many citation-key collisions for {base}")
            key = f"{base}{_DISAMBIGUATION[attempt - 1]}"

        self._by_key[key] = source
        self._by_source_id[source.id] = key
        if key not in self._order:
            self._order.append(key)
        return key

    # ---------------------------------------------------------------- access
    def resolve(self, citation_key: str) -> Source | None:
        """Return the source registered under ``citation_key``, or ``None``."""
        return self._by_key.get(citation_key)

    def citation_key_for_source(self, source_id: str) -> str | None:
        """Return the key assigned to ``source_id``, or ``None`` if not registered."""
        return self._by_source_id.get(source_id)

    def cited_sources(self) -> list[Source]:
        """All cited sources, in registration order."""
        return [self._by_key[key] for key in self._order]

    def known_keys(self) -> set[str]:
        return set(self._by_key)

    def detect_orphan_citations(self, text: str) -> list[str]:
        """Return citation keys found in ``text`` that have no registered source.

        Keys are matched by :data:`CITATION_KEY_PATTERN`; each match not present in
        this manager's registry is reported as an orphan (deduplicated, in order).
        """
        found: list[str] = []
        for match in CITATION_KEY_PATTERN.finditer(text):
            key = match.group(1)
            if key not in self._by_key and key not in found:
                found.append(key)
        return found


def detect_orphan_citations(text: str, known_keys: set[str]) -> list[str]:
    """Scan ``text`` for citation keys absent from ``known_keys``.

    Module-level convenience that does not require a :class:`CitationManager`.
    Useful for auditing a draft against an externally supplied set of valid keys.
    """
    found: list[str] = []
    for match in CITATION_KEY_PATTERN.finditer(text):
        key = match.group(1)
        if key not in known_keys and key not in found:
            found.append(key)
    return found

def detect_internal_tokens(text: str) -> list[str]:
    """Return internal ChatGPT/file citation tokens found in ``text`` (audit A02).

    Academic output must never carry ``turn...``, ``view...``, ``search...``,
    ``filecite`` or the CJK citation brackets (AGENTS.md rules). Tokens are
    reported as found — the caller must reject the output; silently stripping
    them would hide an unknown provenance.
    """
    found: list[str] = []
    for match in INTERNAL_TOKEN_PATTERN.finditer(text):
        token = match.group(0)
        if token not in found:
            found.append(token)
    return found


def known_author_year_forms(sources: list[Source]) -> set[str]:
    """Build the set of legitimate author-year citation forms for ``sources``.

    Includes the bare author-year form plus every locator variant ``p. N`` /
    ``pp. X–Y`` that the audit accepts for that source.
    """
    forms: set[str] = set()
    for source in sources:
        base = format_in_text_author_year(source)
        forms.add(base)
        # Locator variants: "(Smith, 2012, p. 42)" / "(Smith, 2012, pp. 4-6)".
        forms.add(f"{base}, p. *")
    return forms


def detect_orphan_author_year_citations(text: str, known_sources: list[Source]) -> list[str]:
    """Scan ``text`` for author-year citations with no matching source (A02).

    A citation such as ``(Nonexistent, 2024)`` is an orphan when no supplied
    source produces the same author-year form (case-insensitive surname match,
    matching year). Returns the offending citation strings, deduplicated in
    order of first appearance.
    """
    # Map normalized "surname|year" -> known source author-year forms.
    known: set[tuple[str, str]] = set()
    for source in known_sources:
        base = format_in_text_author_year(source)
        year = str(source.year) if source.year is not None else "n.d."
        # Strip locator, then split "Surname et al.," prefix from year.
        if not base.endswith(f", {year}"):
            continue
        name_part = base[: -len(f", {year}")].strip()
        # Accept both "Surname" and "Surname et al." lead tokens, as well as "&"-joined two-author leads.
        lead = name_part.split(" et al.", 1)[0].strip().casefold()
        first_author = lead.split(" & ", 1)[0].strip()
        if lead:
            known.add((lead, year))
        if first_author:
            known.add((first_author, year))
    found: list[str] = []
    for match in AUTHOR_YEAR_CITATION_PATTERN.finditer(text):
        citation = match.group(0)
        name = match.group("name").strip()
        year = match.group("year")
        lead = name.split(" et al.", 1)[0].strip().casefold()
        # "&"-joined two-author citations match on the first author's surname,
        # mirroring the in-text formatter's lead-author logic.
        lead = lead.split(" & ", 1)[0].strip()
        if (lead, year) in known:
            continue
        if citation not in found:
            found.append(citation)
    return found
