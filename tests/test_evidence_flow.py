"""Fast, network-free tests for the evidence-control flow (Phase 5)."""

from __future__ import annotations

from src.schemas.claim import Claim, ClaimImportance, ClaimStatus, SupportLevel
from src.schemas.evidence import (
    Evidence,
    EvidenceRelationship,
    EvidenceStrength,
)
from src.workflows.evidence_flow import (
    calibrate_confidence,
    compute_support_level,
    evaluate_claim,
)


def _claim(*, importance: ClaimImportance = ClaimImportance.HIGH, required: int = 1) -> Claim:
    return Claim(
        claim_text="Test claim",
        importance=importance,
        required_source_count=required,
    )


def _evidence(
    *,
    claim_id: str,
    source_id: str = "src_a",
    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
    strength: EvidenceStrength = EvidenceStrength.MODERATE,
) -> Evidence:
    return Evidence(
        claim_id=claim_id,
        source_id=source_id,
        evidence_text="supporting passage",
        relationship=relationship,
        strength=strength,
    )


# --------------------------------------------------------------------------- #
# compute_support_level
# --------------------------------------------------------------------------- #
def test_support_level_none_when_empty() -> None:
    assert compute_support_level([]) is SupportLevel.NONE


def test_support_level_weak_for_lone_weak() -> None:
    claim = _claim()
    assert compute_support_level([_evidence(claim_id=claim.id, strength=EvidenceStrength.WEAK)]) is SupportLevel.WEAK


def test_support_level_moderate_for_lone_moderate() -> None:
    claim = _claim()
    assert compute_support_level([_evidence(claim_id=claim.id, strength=EvidenceStrength.MODERATE)]) is SupportLevel.MODERATE


def test_support_level_strong_for_definitive() -> None:
    claim = _claim()
    assert compute_support_level([_evidence(claim_id=claim.id, strength=EvidenceStrength.DEFINITIVE)]) is SupportLevel.STRONG


def test_partial_support_degrades_ceiling() -> None:
    claim = _claim()
    evidence = _evidence(
        claim_id=claim.id,
        strength=EvidenceStrength.DEFINITIVE,
        relationship=EvidenceRelationship.PARTIALLY_SUPPORTS,
    )
    # Partially supporting definitive → ceiling degrades to STRONG → MODERATE.
    assert compute_support_level([evidence]) is SupportLevel.MODERATE


# --------------------------------------------------------------------------- #
# evaluate_claim
# --------------------------------------------------------------------------- #
def test_no_evidence_is_insufficient() -> None:
    claim = _claim()
    result = evaluate_claim(claim, [])
    assert result.status is ClaimStatus.INSUFFICIENT_EVIDENCE
    assert result.support_level is SupportLevel.NONE
    assert result.confidence == 0.0


def test_contradiction_without_support_is_refuted() -> None:
    claim = _claim()
    evidence = _evidence(claim_id=claim.id, relationship=EvidenceRelationship.CONTRADICTS)
    result = evaluate_claim(claim, [evidence])
    assert result.status is ClaimStatus.REFUTED
    assert result.confidence == 0.0


def test_conflict_disclosed_when_both_sides() -> None:
    claim = _claim()
    supporting = _evidence(claim_id=claim.id)
    contradicting = _evidence(
        claim_id=claim.id,
        source_id="src_b",
        relationship=EvidenceRelationship.CONTRADICTS,
    )
    result = evaluate_claim(claim, [supporting, contradicting])
    assert result.status is ClaimStatus.CONFLICTED
    assert "conflict" in result.reason.lower()


def test_single_source_satisfies_required_one() -> None:
    claim = _claim(required=1)
    evidence = _evidence(claim_id=claim.id, strength=EvidenceStrength.STRONG)
    result = evaluate_claim(claim, [evidence])
    assert result.status in {ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED}


def test_insufficient_distinct_sources() -> None:
    claim = _claim(required=2)
    evidence = _evidence(claim_id=claim.id)
    result = evaluate_claim(claim, [evidence])
    assert result.status is ClaimStatus.INSUFFICIENT_EVIDENCE
    assert "source" in result.reason.lower()


def test_partial_support_requires_qualifier() -> None:
    claim = _claim(required=1)
    evidence = _evidence(claim_id=claim.id, strength=EvidenceStrength.WEAK)
    result = evaluate_claim(claim, [evidence])
    assert result.status is ClaimStatus.PARTIALLY_SUPPORTED


def test_irrelevant_evidence_is_ignored() -> None:
    claim = _claim(required=1)
    irrelevant = _evidence(claim_id=claim.id, relationship=EvidenceRelationship.IRRELEVANT)
    result = evaluate_claim(claim, [irrelevant])
    assert result.status is ClaimStatus.INSUFFICIENT_EVIDENCE


# --------------------------------------------------------------------------- #
# calibrate_confidence
# --------------------------------------------------------------------------- #
def test_confidence_zero_without_support() -> None:
    claim = _claim()
    assert calibrate_confidence(claim, supporting=[], contradicting=[], support_level=SupportLevel.NONE) == 0.0


def test_confidence_bounded_by_support_level() -> None:
    claim = _claim(required=1)
    supporting = [_evidence(claim_id=claim.id, strength=EvidenceStrength.STRONG)]
    confidence = calibrate_confidence(
        claim, supporting=supporting, contradicting=[], support_level=SupportLevel.MODERATE
    )
    assert confidence <= 0.7


def test_contradiction_reduces_confidence() -> None:
    claim = _claim(required=1)
    supporting = [_evidence(claim_id=claim.id, strength=EvidenceStrength.STRONG)]
    base = calibrate_confidence(
        claim, supporting=supporting, contradicting=[], support_level=SupportLevel.MODERATE
    )
    reduced = calibrate_confidence(
        claim,
        supporting=supporting,
        contradicting=[_evidence(claim_id=claim.id, relationship=EvidenceRelationship.CONTRADICTS)],
        support_level=SupportLevel.MODERATE,
    )
    assert reduced < base
