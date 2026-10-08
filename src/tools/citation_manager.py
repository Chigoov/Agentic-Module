"""Deterministic citation manager with human label disambiguation (Bagian G).

Specification anchors:
  * SYSTEM_RULES.md §E.32 — never invent references during writing.
  * SYSTEM_RULES.md §E.39 — every citation must map to a source.
  * AGENT_CONSTITUTION.md §4 — never cite an unverified source.
  * Bagian G — Unified citation label mapping across writer, references, and audits.
    Same author and year produces (Smith, 2023a) and (Smith, 2023b).
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
    "build_citation_map",
]

#: Matches a machine citation key such as ``smith2012`` or ``smith2012a``.
CITATION_KEY_PATTERN = re.compile(r"(?<![a-zA-Z0-9/])([a-z][a-z0-9]*[0-9]{4}[a-z]?)(?![a-zA-Z0-9])")

#: Internal ChatGPT/file citation tokens that must never survive into output
INTERNAL_TOKEN_PATTERN = re.compile(r"turn\d+|view\d+|search\d+|filecite|[\u3010\u3011]|citeturn")

#: Author-year in-text citation, e.g. (Smith, 2012), (Smith, 2012a), (Smith, 2012, p. 42)
AUTHOR_YEAR_CITATION_PATTERN = re.compile(
    r"\((?P<name>[A-Za-z][A-Za-z .,'&\u2019-]*?),\s*"
    r"(?P<year>\d{4}[a-z]?|n\.d\.(?:-[a-z])?)"
    r"(?P<locator>(?:,\s*[^();]*)?)\)"
)

_DISAMBIGUATION = "abcdefghijklmnopqrstuvwxyz"


def author_year_mentions(text: str):
    for group in re.findall(r"\(([^()]*)\)", text):
        for part in group.split(";"):
            match = AUTHOR_YEAR_CITATION_PATTERN.fullmatch("(" + part.strip() + ")")
            if match:
                yield match


class CitationManager:
    """Registry of cited sources keyed by stable machine key and disambiguated human label."""

    def __init__(self) -> None:
        self._by_key: dict[str, Source] = {}
        self._by_source_id: dict[str, str] = {}
        self._order: list[str] = []
        # Human-facing label state
        self._label_by_id: dict[str, str] = {}
        self._groups: dict[str, list[Source]] = {}

    # ---------------------------------------------------------------- register
    def register_source(self, source: Source) -> str:
        """Register ``source`` and return its (possibly disambiguated) machine key.

        Also updates human-facing citation labels with APA 7 collision suffixes
        ('Smith, 2023a', 'Smith, 2023b') when same author-year occurs.
        """
        # 1. Machine citation key registration
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

        # 2. Human in-text label registration and disambiguation
        base_label = format_in_text_author_year(source)
        if base_label not in self._groups:
            self._groups[base_label] = [source]
            self._label_by_id[source.id] = base_label
        else:
            group = self._groups[base_label]
            if not any(s.id == source.id for s in group):
                group.append(source)
            # If group has > 1 distinct sources, disambiguate all with letters a, b, c...
            if len(group) > 1:
                for idx, s in enumerate(group):
                    suffix = _DISAMBIGUATION[idx % len(_DISAMBIGUATION)]
                    year_str = str(s.year) if s.year is not None else "n.d."
                    # Replace terminal year with year+suffix
                    disambiguated = re.sub(rf"\b{re.escape(year_str)}$", f"{year_str}{suffix}", base_label)
                    self._label_by_id[s.id] = disambiguated

        return key

    # ---------------------------------------------------------------- access
    def resolve(self, citation_key: str) -> Source | None:
        """Return the source registered under ``citation_key``, or ``None``."""
        return self._by_key.get(citation_key)

    def citation_key_for_source(self, source_id: str) -> str | None:
        """Return the key assigned to ``source_id``, or ``None`` if not registered."""
        return self._by_source_id.get(source_id)

    def get_citation_label(self, source_id: str) -> str:
        """Return the human-facing citation label (e.g. 'Smith, 2023a')."""
        if source_id in self._label_by_id:
            return self._label_by_id[source_id]
        src = next((s for s in self._by_key.values() if s.id == source_id), None)
        return format_in_text_author_year(src) if src else "Unknown, n.d."

    def citation_map(self) -> dict[str, str]:
        """Return central mapping of source_id -> citation_label."""
        return dict(self._label_by_id)

    def cited_sources(self) -> list[Source]:
        """All cited sources, in registration order."""
        return [self._by_key[key] for key in self._order]

    def known_keys(self) -> set[str]:
        return set(self._by_key)

    def detect_orphan_citations(self, text: str) -> list[str]:
        """Return citation keys found in ``text`` that have no registered source."""
        # Strip URLs so URL/DOI segments (e.g. .c1386 or /nature14539) are never misread as citation keys
        clean_text = re.sub(r"https?://[^\s)\]]+", "", text)
        found: list[str] = []
        for match in CITATION_KEY_PATTERN.finditer(clean_text):
            key = match.group(1)
            if key not in self._by_key and key not in found:
                found.append(key)
        return found


def detect_orphan_citations(text: str, known_keys: set[str]) -> list[str]:
    """Scan ``text`` for citation keys absent from ``known_keys``."""
    # Strip URLs so URL/DOI segments (e.g. .c1386 or /nature14539) are never misread as citation keys
    clean_text = re.sub(r"https?://[^\s)\]]+", "", text)
    found: list[str] = []
    for match in CITATION_KEY_PATTERN.finditer(clean_text):
        key = match.group(1)
        if key not in known_keys and key not in found:
            found.append(key)
    return found


def detect_internal_tokens(text: str) -> list[str]:
    """Return internal ChatGPT/file citation tokens found in ``text``."""
    found: list[str] = []
    for match in INTERNAL_TOKEN_PATTERN.finditer(text):
        token = match.group(0)
        if token not in found:
            found.append(token)
    return found


def known_author_year_forms(sources: list[Source]) -> set[str]:
    """Build the set of legitimate author-year citation forms for ``sources``."""
    forms: set[str] = set()
    for source in sources:
        base = format_in_text_author_year(source)
        forms.add(base)
        forms.add(f"{base}, p. *")
    return forms


def reconcile_references(draft: str, reference_list, sources: list[Source]) -> dict:
    """Count pointers in the body, independently of the available corpus."""
    body = re.split(r"(?im)^##\s+(?:references|referensi|daftar pustaka)\s*$", draft)[0]
    by_id = {source.id: source for source in sources}
    entries = reference_list.entries if reference_list else []
    manager = CitationManager()
    findings = []
    for entry in entries:
        if entry.source_id not in by_id:
            findings.append(f"reference has no source: {entry.source_id}")
        else:
            manager.register_source(by_id[entry.source_id])
    from src.tools.reference_formatter import format_reference_list
    expected = {entry.source_id: entry.formatted for entry in format_reference_list(manager.cited_sources(), citation_manager=manager).entries}
    if len({entry.source_id for entry in entries}) != len(entries):
        findings.append("duplicate reference entries")
    for entry in entries:
        if entry.source_id in expected and entry.formatted != expected[entry.source_id]:
            findings.append(f"reference metadata does not match source: {entry.source_id}")
    forms = {f"{m.group('name').strip()}, {m.group('year')}" for m in author_year_mentions(body)}
    cited = {source.id for source in manager.cited_sources() if manager.get_citation_label(source.id) in forms}
    for entry in entries:
        if entry.source_id not in cited:
            findings.append(f"reference not cited in body: {entry.source_id}")
    known = set(manager.citation_map().values())
    for form in sorted(forms - known):
        findings.append(f"body citation has no reference: {form}")
    return {"available": len(sources), "cited": len(cited), "cited_source_ids": sorted(cited),
        "reference_entries": len(entries), "findings": findings}


def detect_orphan_author_year_citations(text: str, known_sources: list[Source]) -> list[str]:
    """Scan ``text`` for author-year citations with no matching source.

    Supports disambiguated years like '2023a' matching sources with year 2023.
    """
    known: set[tuple[str, str]] = set()
    for source in known_sources:
        base = format_in_text_author_year(source)
        year = str(source.year) if source.year is not None else "n.d."
        if not base.endswith(f", {year}"):
            continue
        name_part = base[: -len(f", {year}")].strip()
        lead = name_part.split(" et al.", 1)[0].strip().casefold()
        first_author = lead.split(" & ", 1)[0].strip()
        if lead:
            known.add((lead, year))
        if first_author:
            known.add((first_author, year))

    found: list[str] = []
    for match in author_year_mentions(text):
        citation = match.group(0)
        name = match.group("name").strip()
        raw_year = match.group("year")
        base_year = raw_year.rstrip("abcdefghijklmnopqrstuvwxyz")
        lead = name.split(" et al.", 1)[0].strip().casefold()
        lead = lead.split(" & ", 1)[0].strip()

        if (lead, raw_year) in known or (lead, base_year) in known:
            continue
        if citation not in found:
            found.append(citation)
    return found


def build_citation_map(
    *,
    claims: list[Any],
    evidence: list[Any],
    citation_manager: CitationManager,
) -> dict[str, Any]:
    """Build standardized citation_map.json artifact dictionary."""
    citations: list[dict[str, Any]] = []
    evidence_by_claim: dict[str, list[Any]] = {}
    for ev in evidence:
        c_id = getattr(ev, "claim_id", None)
        if c_id:
            evidence_by_claim.setdefault(c_id, []).append(ev)

    seen_entries: set[tuple[str, str, str | None]] = set()

    for claim in claims:
        claim_id = getattr(claim, "id", "")
        claim_evs = evidence_by_claim.get(claim_id, [])

        # 1. Map from evidence items
        for ev in claim_evs:
            src_id = getattr(ev, "source_id", "")
            if not src_id:
                continue
            label = citation_manager.get_citation_label(src_id)
            ev_id = getattr(ev, "id", "")
            loc_obj = getattr(ev, "location", None)
            loc_str = "location unspecified"
            if loc_obj is not None:
                if hasattr(loc_obj, "describe"):
                    loc_str = loc_obj.describe() or "location unspecified"
                elif getattr(loc_obj, "page", None):
                    loc_str = f"p. {loc_obj.page}"
                elif getattr(loc_obj, "locator", None):
                    loc_str = str(loc_obj.locator)

            key = (label, claim_id, ev_id)
            if key not in seen_entries:
                seen_entries.add(key)
                citations.append({
                    "citation_label": label,
                    "source_id": src_id,
                    "claim_id": claim_id,
                    "evidence_id": ev_id,
                    "location": loc_str,
                })

        # 2. Supporting sources without specific evidence
        supporting = getattr(claim, "supporting_sources", []) or []
        for src_id in supporting:
            label = citation_manager.get_citation_label(src_id)
            key = (label, claim_id, None)
            if key not in seen_entries:
                seen_entries.add(key)
                citations.append({
                    "citation_label": label,
                    "source_id": src_id,
                    "claim_id": claim_id,
                    "evidence_id": None,
                    "location": "source",
                })

    return {"citations": citations}
