"""Academic integrity gate — referential and evidence checks before writing.
Specification anchors:
  * AGENT_CONSTITUTION.md §6–§10 — evidence integrity; status input is not proof.
  * SYSTEM_RULES.md §E.31 — writer works from approved claims only.
  * SYSTEM_RULES.md §E.39 — every citation must map to a source.
  * AGENTS.md — academic output must not contain internal citation tokens.
Audit findings closed here (docs/audit_independen_2026-09-07/LAPORAN_AUDIT.md):
  * A01 — claim/evidence/source IDs from untrusted input passed verification:
    a claim marked SUPPORTED with a nonexistent evidence ID reached the final
    DOCX. The gate validates referential integrity and source verification
    state before any stage runs.
  * A02 — the citation audit only scanned machine keys, so author-year orphans
    and internal tokens survived. Token and author-year orphan scanning now
    runs on the full draft text at the same gate.
  * A04 — CONFLICTED claims were writable without any disclosure mechanism;
    the gate requires a qualifier (structured disclosure) or contradiction
    evidence actually present before a conflicted claim may be written.
Status flags on the input JSON are *not* evidence. What the gate trusts:
  * IDs that actually resolve within the payload,
  * source verification state recorded by the verification engine,
  * verbatim evidence that can be re-checked (quote verification against a
    retrieved snapshot happens in the retrieval/evidence pipeline, so a
    verbatim quote whose source carries no verification evidence is rejected).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from src.core.errors import HumanReviewRequired
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence, SUPPORTING_RELATIONSHIPS
from src.schemas.source import Source, is_verified
from src.tools.citation_manager import (
    detect_internal_tokens,
    detect_orphan_author_year_citations,
)
__all__ = ["AcademicGateError", "GateResult", "check_academic_integrity", "scan_output_text"]
@dataclass
class GateResult:
    """Structured outcome of the academic integrity gate."""
    violations: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    @property
    def ok(self) -> bool:
        return not self.violations and not self.review_reasons
class AcademicGateError(HumanReviewRequired):
    """The academic integrity gate rejected the payload before writing.
    Raised as :class:`HumanReviewRequired` so CLI/API surface a structured
    review request instead of a bare failure.
    """
def check_academic_integrity(
    *,
    claims: list[Claim],
    evidence: list[Evidence],
    sources: list[Source],
) -> GateResult:
    """Validate referential integrity and evidence quality before writing.
    Checks (each maps to an audit finding):
    1. Every claim/evidence/source ID referenced must exist (A01).
    2. Evidence must point at a claim that exists, and both sides agree on the
       relation (an evidence record whose claim_id is unknown is a violation).
    3. Cited sources must carry a verified state recorded by the verification
       engine (A01: input status flags are not proof; a source that never went
       through verification is not citable).
    4. Important claims must have supporting evidence attached (A01).
    5. CONFLICTED claims must be disclosed: either a qualifier is present or
       contradicting evidence is actually attached (A04).
    6. A verbatim quotation must be traceable: its source must be verified
       (A01/A02: a quote flag alone is not proof).
    """
    result = GateResult()
    source_by_id = {source.id: source for source in sources}
    claim_by_id = {claim.id: claim for claim in claims}
    evidence_ids = [evidence.id for evidence in evidence]
    # -- 1. Referential integrity: evidence IDs referenced by claims must exist.
    for claim in claims:
        for evidence_id in claim.supporting_evidence:
            if evidence_id not in evidence_ids:
                result.violations.append(
                    f"claim {claim.id} references nonexistent supporting evidence {evidence_id}"
                )
        for evidence_id in claim.contradicting_evidence:
            if evidence_id not in evidence_ids:
                result.violations.append(
                    f"claim {claim.id} references nonexistent contradicting evidence {evidence_id}"
                )
        for source_id in claim.supporting_sources:
            if source_id not in source_by_id:
                result.violations.append(
                    f"claim {claim.id} references nonexistent source {source_id}"
                )
    # Duplicate evidence IDs are ambiguous bookkeeping and rejected outright.
    if len(evidence_ids) != len(set(evidence_ids)):
        result.violations.append("duplicate evidence IDs in payload")
    # -- 2. Evidence -> claim/source references must resolve.
    for item in evidence:
        if item.claim_id not in claim_by_id:
            result.violations.append(
                f"evidence {item.id} references nonexistent claim {item.claim_id}"
            )
            continue
        if item.source_id not in source_by_id:
            result.violations.append(
                f"evidence {item.id} references nonexistent source {item.source_id}"
            )
    # -- 3. Cited sources must be verified by the engine, not merely flagged.
    cited_source_ids: set[str] = set()
    for claim in claims:
        cited_source_ids.update(claim.supporting_sources)
    for item in evidence:
        cited_source_ids.add(item.source_id)
    for source_id in sorted(cited_source_ids):
        source = source_by_id.get(source_id)
        if source is None:
            continue  # already reported as a missing reference
        if not is_verified(source.state):
            result.violations.append(
                f"source {source_id} cited but never verified (state={source.state})"
            )
    # -- 4. Important claims must have supporting evidence.
    for claim in claims:
        if claim.is_important and not claim.supporting_evidence:
            result.violations.append(
                f"important claim {claim.id} has no supporting evidence"
            )
    # -- 5. Conflicted claims must disclose the conflict (A04).
    for claim in claims:
        if str(claim.status) != "CONFLICTED":
            continue
        if claim.qualifier:
            continue
        contradictions = [
            item
            for item in evidence
            if item.claim_id == claim.id
            and item.relationship not in SUPPORTING_RELATIONSHIPS
        ]
        if not contradictions:
            result.violations.append(
                f"conflicted claim {claim.id} carries no disclosure: "
                "add a qualifier or attach the contradicting evidence"
            )
    # -- 6. Verbatim quotes must come from a verified source.
    for item in evidence:
        if not item.verbatim:
            continue
        source = source_by_id.get(item.source_id)
        if source is not None and not is_verified(source.state):
            result.violations.append(
                f"verbatim quote in evidence {item.id} cites unverified source {item.source_id}"
            )
    return result
def scan_output_text(
    *,
    draft: str,
    sources: list[Source],
) -> list[str]:
    """Scan final output text for internal tokens and orphan citations (A02).
    Returns violations; a non-empty result must block export. Internal tokens
    are never stripped silently — the offending provenance is unknown, so the
    writer must fail loudly instead.
    """
    violations: list[str] = []
    tokens = detect_internal_tokens(draft)
    if tokens:
        violations.append(f"internal citation tokens present in draft: {tokens}")
    orphans = detect_orphan_author_year_citations(draft, sources)
    if orphans:
        violations.append(f"author-year citations with no matching source: {orphans}")
    return violations
