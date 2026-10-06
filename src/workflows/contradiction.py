"""Contradiction detection workflow.

Specification anchors:
  * AGENT_CONSTITUTION.md §14 — conflicts must not be hidden.
  * Requirement 11 — Contradiction Detection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.schemas.claim import Claim
from src.schemas.evidence import (
    SUPPORTING_RELATIONSHIPS,
    Evidence,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
)

__all__ = [
    "ContradictoryFinding",
    "NullFinding",
    "ContradictionReport",
    "detect_contradictions",
]


@dataclass
class ContradictoryFinding:
    """A located finding that contradicts a claim."""

    evidence_id: str
    source_id: str
    excerpt: str  # first 200 characters of evidence text


@dataclass
class NullFinding:
    """A finding indicating absence of support (NOT_SUPPORTED)."""

    evidence_id: str
    source_id: str
    excerpt: str


@dataclass
class ContradictionReport:
    """Structured analysis of contradictions and null findings for a claim."""

    claim_id: str
    has_mixed_evidence: bool
    conflict_severity: str | None  # "HIGH", "MEDIUM", "LOW", or None
    contradictory_findings: list[ContradictoryFinding]
    null_findings: list[NullFinding]

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to JSON-compatible dictionary."""
        return {
            "claim_id": self.claim_id,
            "has_mixed_evidence": self.has_mixed_evidence,
            "conflict_severity": self.conflict_severity,
            "contradictory_findings": [asdict(f) for f in self.contradictory_findings],
            "null_findings": [asdict(f) for f in self.null_findings],
        }

    def to_text(self) -> str:
        """Human-readable representation of contradiction report."""
        lines: list[str] = [
            f"Contradiction Report for Claim: {self.claim_id}",
            f"Mixed Evidence: {'Yes' if self.has_mixed_evidence else 'No'}",
            f"Conflict Severity: {self.conflict_severity or 'None'}",
        ]
        if self.contradictory_findings:
            lines.append(f"\nContradictory Findings ({len(self.contradictory_findings)}):")
            for cf in self.contradictory_findings:
                lines.append(f"  - [{cf.evidence_id}] from source {cf.source_id}: {cf.excerpt}")
        if self.null_findings:
            lines.append(f"\nNull Findings ({len(self.null_findings)}):")
            for nf in self.null_findings:
                lines.append(f"  - [{nf.evidence_id}] from source {nf.source_id}: {nf.excerpt}")
        return "\n".join(lines)


def detect_contradictions(
    claim: Claim,
    evidence: list[Evidence],
) -> ContradictionReport:
    """Detect mixed, contradictory, and null evidence for a claim.

    Parameters
    ----------
    claim:
        The Claim to evaluate.
    evidence:
        Evidence records. Relevant records are filtered by claim.id or claim's
        supporting/contradicting evidence lists.

    Returns
    -------
    ContradictionReport
        Structured report classifying mixed evidence, severity, and findings.
    """
    relevant = [
        e
        for e in evidence
        if (
            e.claim_id == claim.id
            or e.id in claim.supporting_evidence
            or e.id in claim.contradicting_evidence
        )
    ]
    # Fallback if caller passed pre-associated evidence where claim_id is not set
    if not relevant and evidence and all(not e.claim_id for e in evidence):
        relevant = list(evidence)

    # Mixed evidence: at least one supporting and at least one contradictory
    has_supporting = any(e.relationship in SUPPORTING_RELATIONSHIPS for e in relevant)
    has_contradicting = any(
        e.relationship is EvidenceRelationship.CONTRADICTS
        or e.evidence_type is EvidenceType.CONTRADICTORY
        for e in relevant
    )
    has_mixed_evidence = has_supporting and has_contradicting

    # Contradictory findings
    contradictory_evidence = [
        e
        for e in relevant
        if (
            e.evidence_type is EvidenceType.CONTRADICTORY
            or e.relationship is EvidenceRelationship.CONTRADICTS
        )
    ]
    contradictory_findings = [
        ContradictoryFinding(
            evidence_id=e.id,
            source_id=e.source_id,
            excerpt=e.evidence_text[:200],
        )
        for e in contradictory_evidence
    ]

    # Null findings: evidence_type is NOT_SUPPORTED
    null_findings = [
        NullFinding(
            evidence_id=e.id,
            source_id=e.source_id,
            excerpt=e.evidence_text[:200],
        )
        for e in relevant
        if e.evidence_type is EvidenceType.NOT_SUPPORTED
    ]

    # Conflict severity:
    # HIGH if any contradictory evidence has strength STRONG or DEFINITIVE
    # MEDIUM if any has MODERATE
    # LOW if WEAK
    # None if no contradictory findings
    conflict_severity: str | None = None
    if contradictory_evidence:
        strengths = {e.strength for e in contradictory_evidence}
        if (
            EvidenceStrength.DEFINITIVE in strengths
            or EvidenceStrength.STRONG in strengths
        ):
            conflict_severity = "HIGH"
        elif EvidenceStrength.MODERATE in strengths:
            conflict_severity = "MEDIUM"
        elif EvidenceStrength.WEAK in strengths:
            conflict_severity = "LOW"

    return ContradictionReport(
        claim_id=claim.id,
        has_mixed_evidence=has_mixed_evidence,
        conflict_severity=conflict_severity,
        contradictory_findings=contradictory_findings,
        null_findings=null_findings,
    )
