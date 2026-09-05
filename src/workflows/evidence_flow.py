"""Evidence-control flow: classify support, detect conflict, and calibrate confidence.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §19 — evidence strength rule (wording ≤ evidence).
  * AGENT_CONSTITUTION.md §6–§10 — evidence integrity.
  * AGENT_CONSTITUTION.md §14 — conflicts must not be hidden.
  * AGENT_CONSTITUTION.md §29–§30 — unsupported/insufficient claims are revised,
    removed, or escalated; never fabricated.

This module is *pure logic*: it takes a :class:`~src.schemas.claim.Claim` and the
:class:`~src.schemas.evidence.Evidence` records attached to it, and produces a
deterministic verdict. It performs no I/O and invokes no model, so the entire
classification can be unit-tested offline.

The :class:`~src.schemas.claim.Claim` schema already guards the two invariants
that matter most (a claim cannot become SUPPORTED without evidence, and cannot be
quietly SUPPORTED while carrying contradictions). This module supplies the
*reasoning* that decides which status a claim should actually hold.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import (
    SUPPORTING_RELATIONSHIPS,
    Evidence,
    EvidenceRelationship,
    EvidenceStrength,
)

__all__ = [
    "EvaluationResult",
    "evaluate_claim",
    "classify_relationship",
    "compute_support_level",
    "calibrate_confidence",
]

#: Weight of each evidence strength when aggregating into a support level.
_STRENGTH_WEIGHT: dict[EvidenceStrength, int] = {
    EvidenceStrength.WEAK: 1,
    EvidenceStrength.MODERATE: 2,
    EvidenceStrength.STRONG: 3,
    EvidenceStrength.DEFINITIVE: 4,
}


@dataclass(frozen=True)
class EvaluationResult:
    """Deterministic verdict for one claim given its attached evidence.

    Attributes
    ----------
    status:
        Recommended :class:`~src.schemas.claim.ClaimStatus`.
    support_level:
        Aggregate strength of the supporting evidence.
    confidence:
        Calibrated confidence in ``[0.0, 1.0]`` that the claim, as worded, is
        carried by the evidence. Never exceeds the strength of the evidence.
    reason:
        Human-readable explanation, mandatory for the audit trail.
    """

    status: ClaimStatus
    support_level: SupportLevel
    confidence: float
    reason: str


def classify_relationship(evidence: Evidence) -> EvidenceRelationship:
    """Return the relationship of ``evidence`` (passthrough for test clarity)."""
    return evidence.relationship


def compute_support_level(supporting: list[Evidence]) -> SupportLevel:
    """Aggregate supporting evidence into a single :class:`SupportLevel`.

    Rules (deterministic and testable):

    * no supporting evidence → ``NONE``;
    * best ceiling ``WEAK`` → ``WEAK``;
    * best ceiling ``MODERATE`` → ``MODERATE`` (its own ceiling);
    * best ceiling ``STRONG`` → ``MODERATE`` for a single source, ``STRONG`` when
      corroborated by ≥2 distinct sources;
    * best ceiling ``DEFINITIVE`` → ``STRONG`` (a meta-analysis/systematic review
      alone is enough).

    A partially-supporting piece is already degraded one notch by
    :meth:`Evidence.max_claim_strength` (00_MASTER_INSTRUCTION.md §19).
    """
    if not supporting:
        return SupportLevel.NONE

    best_weight = max(_STRENGTH_WEIGHT[e.max_claim_strength()] for e in supporting)
    distinct_sources = {e.source_id for e in supporting}

    if best_weight >= _STRENGTH_WEIGHT[EvidenceStrength.DEFINITIVE]:
        return SupportLevel.STRONG
    if best_weight >= _STRENGTH_WEIGHT[EvidenceStrength.STRONG]:
        return SupportLevel.STRONG if len(distinct_sources) >= 2 else SupportLevel.MODERATE
    if best_weight >= _STRENGTH_WEIGHT[EvidenceStrength.MODERATE]:
        return SupportLevel.MODERATE
    return SupportLevel.WEAK


def calibrate_confidence(
    claim: Claim,
    *,
    supporting: list[Evidence],
    contradicting: list[Evidence],
    support_level: SupportLevel,
) -> float:
    """Produce a confidence in ``[0.0, 1.0]`` that the claim is carried.

    Calibration is deliberately conservative: confidence can never exceed the
    strength of the best evidence, and it is reduced (never raised) by unmet
    source requirements, partial support, and contradiction.
    """
    if not supporting:
        return 0.0

    # Base strength of the strongest warrant.
    strength_to_ceiling: dict[SupportLevel, float] = {
        SupportLevel.NONE: 0.0,
        SupportLevel.WEAK: 0.4,
        SupportLevel.MODERATE: 0.7,
        SupportLevel.STRONG: 0.9,
    }
    confidence = strength_to_ceiling[support_level]

    # Distinct-source requirement (SYSTEM_RULES §C.20 / AGENT_CONSTITUTION §17).
    distinct_sources = {evidence.source_id for evidence in supporting}
    unmet = claim.unmet_source_requirement()
    if claim.required_source_count > 0:
        source_ratio = len(distinct_sources) / claim.required_source_count
        confidence = min(confidence, 0.35 + 0.55 * source_ratio)
    if unmet > 0:
        confidence *= 0.5 ** unmet

    # Partial support is weaker than full support.
    fully_supporting = [
        evidence
        for evidence in supporting
        if evidence.relationship is EvidenceRelationship.SUPPORTS
    ]
    if not fully_supporting:
        confidence *= 0.7

    # Contradiction materially reduces confidence (never hidden; §14).
    if contradicting:
        confidence *= 0.4

    return round(max(0.0, min(1.0, confidence)), 3)


def evaluate_claim(
    claim: Claim,
    evidence: list[Evidence],
    *,
    min_sources: int | None = None,
) -> EvaluationResult:
    """Classify a claim given the evidence currently attached to it.

    Parameters
    ----------
    claim:
        The claim to evaluate.
    evidence:
        All :class:`~src.schemas.evidence.Evidence` records attached to the claim
        (the caller is responsible for passing only evidence whose ``claim_id``
        matches). Records with relationship ``IRRELEVANT`` are ignored.
    min_sources:
        Optional override for ``claim.required_source_count``.

    Returns
    -------
    EvaluationResult
        The recommended status, support level, confidence, and reason.
    """
    relevant = [e for e in evidence if e.relationship is not EvidenceRelationship.IRRELEVANT]
    supporting = [e for e in relevant if e.relationship in SUPPORTING_RELATIONSHIPS]
    contradicting = [e for e in relevant if e.relationship is EvidenceRelationship.CONTRADICTS]

    support_level = compute_support_level(supporting)
    confidence = calibrate_confidence(
        claim,
        supporting=supporting,
        contradicting=contradicting,
        support_level=support_level,
    )

    distinct_sources = {e.source_id for e in supporting}
    if min_sources is not None:
        required = min_sources
    else:
        required = claim.required_source_count

    # Order matters: conflict and refutation dominate, then sufficiency.
    if contradicting and supporting:
        return EvaluationResult(
            status=ClaimStatus.CONFLICTED,
            support_level=support_level,
            confidence=confidence,
            reason=(
                f"{len(supporting)} supporting vs {len(contradicting)} contradicting "
                "evidence; conflict disclosed, not hidden"
            ),
        )

    if contradicting and not supporting:
        return EvaluationResult(
            status=ClaimStatus.REFUTED,
            support_level=SupportLevel.NONE,
            confidence=0.0,
            reason=f"{len(contradicting)} contradicting evidence and none supporting",
        )

    if not supporting:
        return EvaluationResult(
            status=ClaimStatus.INSUFFICIENT_EVIDENCE,
            support_level=SupportLevel.NONE,
            confidence=0.0,
            reason="No supporting evidence attached",
        )

    if len(distinct_sources) < required:
        return EvaluationResult(
            status=ClaimStatus.INSUFFICIENT_EVIDENCE,
            support_level=support_level,
            confidence=confidence,
            reason=(
                f"Only {len(distinct_sources)} distinct source(s) support the claim; "
                f"{required} required"
            ),
        )

    if support_level is SupportLevel.STRONG:
        return EvaluationResult(
            status=ClaimStatus.SUPPORTED,
            support_level=support_level,
            confidence=confidence,
            reason=f"Supported by {len(distinct_sources)} source(s) with strong evidence",
        )

    if support_level in {SupportLevel.WEAK, SupportLevel.MODERATE}:
        return EvaluationResult(
            status=ClaimStatus.PARTIALLY_SUPPORTED,
            support_level=support_level,
            confidence=confidence,
            reason=(
                f"Evidence supports the claim but only at {support_level.value} strength; "
                "wording must be qualified (00_MASTER_INSTRUCTION.md §19)"
            ),
        )

    return EvaluationResult(
        status=ClaimStatus.SUPPORTED,
        support_level=support_level,
        confidence=confidence,
        reason=f"Supported by {len(distinct_sources)} source(s)",
    )
