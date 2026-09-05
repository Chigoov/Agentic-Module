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
from src.tools.reference_formatter import citation_key_for

__all__ = ["CitationManager", "CITATION_KEY_PATTERN", "detect_orphan_citations"]

#: Matches a machine citation key such as ``smith2012`` or ``smith2012a``.
CITATION_KEY_PATTERN = re.compile(r"(?<![a-zA-Z0-9])([a-z][a-z0-9]*[0-9]{4}[a-z]?)(?![a-zA-Z0-9])")

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
