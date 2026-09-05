"""Evidence extraction from retrieved full text.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §15 — evidence registry minimum fields.
  * AGENT_CONSTITUTION.md §8/§9 — never fabricate evidence, page numbers, or
    locations; verbatim quotations must be verifiable by string match.

This module implements the **deterministic** half of extraction: locating a
verbatim passage inside retrieved content and building an :class:`Evidence`
record with an exact character span. It deliberately does **not** call a model
to paraphrase or to decide which passage is relevant — that judgment belongs to
an agent (Phase 6+). When the caller has no verbatim span (e.g. a model summary),
it returns a ``MODEL_PARAPHRASE`` record that is marked non-verbatim and therefore
never eligible for direct quotation.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
)
from src.schemas.source import Source

__all__ = [
    "ExtractionResult",
    "EvidenceExtractor",
    "extract_verbatim",
]


def _normalize(text: str) -> str:
    """Collapse whitespace so matching is tolerant of line wrapping."""
    return " ".join(text.split())


@dataclass(frozen=True)
class ExtractionResult:
    """Outcome of an extraction attempt.

    Attributes
    ----------
    evidence:
        The constructed record, or ``None`` when no verbatim span was found.
    found:
        Whether the passage was located verbatim.
    error:
        Explanation when ``found`` is ``False``.
    """

    evidence: Evidence | None
    found: bool
    error: str | None = None


class EvidenceExtractor:
    """Build :class:`Evidence` records from retrieved content.

    The extractor is stateless and network-free; retrieved text is passed in as
    a string. Verbatim extraction requires exact containment (after whitespace
    normalization); anything else is refused rather than guessed
    (AGENT_CONSTITUTION.md §8).
    """

    def extract_verbatim(
        self,
        *,
        passage: str,
        haystack: str,
        claim_id: str,
        source: Source,
        relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
        strength: EvidenceStrength = EvidenceStrength.MODERATE,
        confidence: float = 1.0,
        location: EvidenceLocation | None = None,
    ) -> ExtractionResult:
        """Extract ``passage`` only if it occurs verbatim in ``haystack``.

        Returns
        -------
        ExtractionResult
            With ``found=True`` and a verified :class:`Evidence` when the passage
            was located; otherwise ``found=False`` with a descriptive ``error``.
        """
        passage = (passage or "").strip()
        if not passage:
            return ExtractionResult(
                evidence=None,
                found=False,
                error="Passage is empty",
            )

        normalized_passage = _normalize(passage)
        normalized_haystack = _normalize(haystack)
        if normalized_passage not in normalized_haystack:
            return ExtractionResult(
                evidence=None,
                found=False,
                error="Passage not found verbatim in retrieved content",
            )

        resolved_location = location or EvidenceLocation()
        evidence = Evidence(
            claim_id=claim_id,
            source_id=source.id,
            evidence_text=passage,
            location=resolved_location,
            relationship=relationship,
            strength=strength,
            confidence=confidence,
            extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
            verbatim=True,
            quote_verified=True,
            extracted_by="evidence_extractor",
        )
        # Re-verify via the schema's own check to keep a single source of truth.
        evidence.mark_quote_verified(haystack=haystack, actor="evidence_extractor")
        return ExtractionResult(evidence=evidence, found=True)

    def record_paraphrase(
        self,
        *,
        text: str,
        claim_id: str,
        source: Source,
        relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
        strength: EvidenceStrength = EvidenceStrength.MODERATE,
        confidence: float,
        notes: str | None = None,
    ) -> Evidence:
        """Record a model-written paraphrase, explicitly non-verbatim.

        A paraphrase can never be presented as a direct quotation
        (AGENT_CONSTITUTION.md §8), so the record is forced non-verbatim and its
        ``quote_verified`` stays ``False``.
        """
        evidence = Evidence(
            claim_id=claim_id,
            source_id=source.id,
            evidence_text=text,
            relationship=relationship,
            strength=strength,
            confidence=confidence,
            extraction_method=ExtractionMethod.MODEL_PARAPHRASE,
            verbatim=False,
            quote_verified=False,
            extracted_by="evidence_extractor",
            notes=notes,
        )
        return evidence


def extract_verbatim(
    *,
    passage: str,
    haystack: str,
    claim_id: str,
    source: Source,
    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
    strength: EvidenceStrength = EvidenceStrength.MODERATE,
    confidence: float = 1.0,
    location: EvidenceLocation | None = None,
) -> ExtractionResult:
    """Module-level convenience wrapper around :meth:`EvidenceExtractor.extract_verbatim`."""
    return EvidenceExtractor().extract_verbatim(
        passage=passage,
        haystack=haystack,
        claim_id=claim_id,
        source=source,
        relationship=relationship,
        strength=strength,
        confidence=confidence,
        location=location,
    )
