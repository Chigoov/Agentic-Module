"""Evidence verification audit workflow.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §10 — validation level C.
  * AGENT_CONSTITUTION.md §8–§9 — never fabricate evidence or quotes.
  * Requirement 8 — Evidence Verification Audit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.schemas.evidence import (
    Evidence,
    EvidenceRelationship,
    EvidenceType,
    ExtractionMethod,
    ReadingDepth,
)
from src.schemas.source import Source, is_verified
from src.schemas.verification import VerificationReport

__all__ = ["AuditFlag", "AuditResult", "audit_evidence"]


@dataclass
class AuditFlag:
    """Individual issue or inconsistency flagged during evidence audit."""

    evidence_id: str
    flag_type: str
    detail: str


@dataclass
class AuditResult:
    """Structured result of an evidence verification audit."""

    total_evidence: int
    by_evidence_type: dict[str, int]
    by_reading_depth: dict[str, int]
    verified_quotes: int
    unverified_quotes: int
    flags: list[AuditFlag]

    def to_dict(self) -> dict[str, Any]:
        """Convert audit result to JSON-serializable dictionary."""
        return {
            "total_evidence": self.total_evidence,
            "by_evidence_type": dict(self.by_evidence_type),
            "by_reading_depth": dict(self.by_reading_depth),
            "verified_quotes": self.verified_quotes,
            "unverified_quotes": self.unverified_quotes,
            "flags": [asdict(f) for f in self.flags],
        }

    def to_text(self) -> str:
        """Generate human-readable summary of the audit result."""
        lines: list[str] = [
            "Evidence Verification Audit",
            "=" * 40,
            f"Total Evidence: {self.total_evidence}",
            f"Verified Quotes: {self.verified_quotes}",
            f"Unverified Quotes: {self.unverified_quotes}",
            f"Total Flags: {len(self.flags)}",
            "",
            "By Evidence Type:",
        ]
        for etype, count in self.by_evidence_type.items():
            if count > 0:
                lines.append(f"  - {etype}: {count}")
        lines.append("")
        lines.append("By Reading Depth:")
        for depth, count in self.by_reading_depth.items():
            if count > 0:
                lines.append(f"  - {depth}: {count}")

        if self.flags:
            lines.append("")
            lines.append("Audit Flags:")
            for flag in self.flags:
                lines.append(f"  - [{flag.flag_type}] ({flag.evidence_id}): {flag.detail}")
        else:
            lines.append("\nNo audit flags detected.")

        return "\n".join(lines)


def audit_evidence(
    evidence: list[Evidence],
    sources: list[Source],
    reports: list[VerificationReport] | None = None,
) -> AuditResult:
    """Perform a comprehensive verification audit on evidence records.

    Parameters
    ----------
    evidence:
        List of Evidence records to audit.
    sources:
        List of Source records referenced by evidence.
    reports:
        Optional list of VerificationReports for deeper corroboration.

    Returns
    -------
    AuditResult
        Aggregated statistics and granular audit flags.
    """
    source_map: dict[str, Source] = {s.id: s for s in sources}
    flags: list[AuditFlag] = []

    # Summary statistics
    by_evidence_type: dict[str, int] = {et.value: 0 for et in EvidenceType}
    by_reading_depth: dict[str, int] = {rd.value: 0 for rd in ReadingDepth}
    verified_quotes = 0
    unverified_quotes = 0

    for e in evidence:
        # Increment counts
        etype_key = e.evidence_type.value if hasattr(e.evidence_type, "value") else str(e.evidence_type)
        rd_key = e.reading_depth.value if hasattr(e.reading_depth, "value") else str(e.reading_depth)
        by_evidence_type[etype_key] = by_evidence_type.get(etype_key, 0) + 1
        by_reading_depth[rd_key] = by_reading_depth.get(rd_key, 0) + 1

        if e.quote_verified:
            verified_quotes += 1
        elif e.verbatim:
            unverified_quotes += 1

        # Check 1: unverified_verbatim
        if e.verbatim and not e.quote_verified:
            flags.append(
                AuditFlag(
                    evidence_id=e.id,
                    flag_type="unverified_verbatim",
                    detail=f"Evidence {e.id} is verbatim but quote_verified is False",
                )
            )

        # Check 2: depth_method_mismatch
        if (
            e.reading_depth is ReadingDepth.ABSTRACT_ONLY
            and e.extraction_method is ExtractionMethod.VERBATIM_FULLTEXT
        ):
            flags.append(
                AuditFlag(
                    evidence_id=e.id,
                    flag_type="depth_method_mismatch",
                    detail=(
                        f"Evidence {e.id} has reading_depth ABSTRACT_ONLY "
                        "but extraction_method VERBATIM_FULLTEXT"
                    ),
                )
            )

        # Check 3: type_relationship_mismatch
        if (
            e.evidence_type is EvidenceType.CONTRADICTORY
            and e.relationship is EvidenceRelationship.SUPPORTS
        ):
            flags.append(
                AuditFlag(
                    evidence_id=e.id,
                    flag_type="type_relationship_mismatch",
                    detail=(
                        f"Evidence {e.id} has evidence_type CONTRADICTORY "
                        "but relationship SUPPORTS"
                    ),
                )
            )

        # Check 4: source verification state consistency
        if e.source_id not in source_map:
            flags.append(
                AuditFlag(
                    evidence_id=e.id,
                    flag_type="source_not_found",
                    detail=f"Evidence {e.id} cites non-existent source {e.source_id}",
                )
            )
        else:
            source = source_map[e.source_id]
            if not is_verified(source.state):
                flags.append(
                    AuditFlag(
                        evidence_id=e.id,
                        flag_type="source_unverified",
                        detail=(
                            f"Evidence {e.id} cites source {source.id} "
                            f"in unverified state {source.state}"
                        ),
                    )
                )

    return AuditResult(
        total_evidence=len(evidence),
        by_evidence_type=by_evidence_type,
        by_reading_depth=by_reading_depth,
        verified_quotes=verified_quotes,
        unverified_quotes=unverified_quotes,
        flags=flags,
    )
