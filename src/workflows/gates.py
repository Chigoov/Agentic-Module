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

import re
from pathlib import Path
from dataclasses import dataclass, field

from src.core.errors import HumanReviewRequired
from src.schemas.claim import Claim
from src.schemas.outline import SECTION_ALIASES, canonical_section
from src.schemas.evidence import (
    Evidence,
    EvidenceRelationship,
    EvidenceType,
    ReadingDepth,
    SUPPORTING_RELATIONSHIPS,
)
from src.schemas.source import RetrievalStatus, Source, is_verified
from src.tools.source_content import inspect_source, recheck_quote, stored_metadata
from src.tools.citation_manager import (
    detect_internal_tokens,
    detect_orphan_author_year_citations,
)

__all__ = [
    "AcademicGateError",
    "DOI_PATTERN",
    "GateResult",
    "check_academic_integrity",
    "create_review_queue_from_gate_result",
    "scan_output_text",
]

DOI_PATTERN = re.compile(r"^10\.\d{4,}/\S+$")
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
def check_input_references(*, claims, evidence, sources, outline=None) -> GateResult:
    """Check the original corpus before access/scientific screening can hide IDs."""
    result = GateResult()
    source_ids, claim_ids = {s.id for s in sources}, {c.id for c in claims}
    by_evidence = {e.id: e for e in evidence}
    for label, records in (("source", sources), ("claim", claims), ("evidence", evidence)):
        if len(records) != len({r.id for r in records}):
            result.violations.append(f"duplicate {label} IDs in payload")
    for claim in claims:
        for eid in claim.supporting_evidence + claim.contradicting_evidence:
            item = by_evidence.get(eid)
            if item is None:
                kind = "supporting" if eid in claim.supporting_evidence else "contradicting"
                result.violations.append(f"claim {claim.id} references nonexistent {kind} evidence {eid}")
            elif item.claim_id != claim.id:
                result.violations.append(f"claim {claim.id}/evidence {eid} claim_id mismatch")
        for sid in claim.supporting_sources:
            if sid not in source_ids:
                result.violations.append(f"claim {claim.id} references nonexistent source {sid}")
    for item in evidence:
        if item.claim_id not in claim_ids:
            result.violations.append(f"evidence {item.id} references nonexistent claim {item.claim_id}")
        if item.source_id not in source_ids:
            result.violations.append(f"evidence {item.id} references nonexistent source {item.source_id}")
    if outline:
        def visit(sections):
            for section in sections:
                for cid in section.claim_ids:
                    if cid not in claim_ids:
                        result.violations.append(f"outline section {section.title!r} references nonexistent claim {cid}")
                visit(section.subsections)
        visit(outline.sections)
    return result

def check_academic_integrity(
    *,
    claims: list[Claim],
    evidence: list[Evidence],
    sources: list[Source],
    root: Path | None = None,
    outline=None,
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
    result = check_input_references(claims=claims, evidence=evidence, sources=sources, outline=outline)
    if outline:
        for claim in claims:
            if claim.id in outline.claim_ids and not claim.is_writable:
                result.review_reasons.append(f"outline requires non-writable claim {claim.id}; revise the claim or outline explicitly")
    source_by_id = {source.id: source for source in sources}
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
        if not is_verified(source.state) or not stored_metadata(source):
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
    # Source reading labels are claims that require an examination artifact.
    for source_id in sorted(cited_source_ids):
        source = source_by_id.get(source_id)
        if source and source.reading_depth == ReadingDepth.FULL_TEXT:
            proof = inspect_source(source, root)
            if not proof["fully_read"]:
                result.review_reasons.append(f"source {source_id} FULL_TEXT lacks validated retrieval/examination proof")

    # -- 6. Recompute all verbatim quotes, including ordinary claims.
    for item in evidence:
        if not item.verbatim:
            continue
        source = source_by_id.get(item.source_id)
        if source is not None and not recheck_quote(source, item, root):
            result.violations.append(f"verbatim evidence {item.id} quote is not found in the located source snapshot")
        if source is not None and not is_verified(source.state):
            result.violations.append(
                f"verbatim quote in evidence {item.id} cites unverified source {item.source_id}"
            )

    # -- 7. DOI format validation (Req 10.1, 10.2, Property 12).
    for source in sources:
        if source.doi is not None and not DOI_PATTERN.match(source.doi):
            result.violations.append(
                f"invalid DOI format for source {source.id}: {source.doi}"
            )

    # -- 8. Evidence type / relationship mismatch (Req 10.3, Property 13).
    for item in evidence:
        if (
            item.evidence_type == EvidenceType.CONTRADICTORY
            and item.relationship == EvidenceRelationship.SUPPORTS
        ):
            result.violations.append(
                f"evidence type/relationship mismatch for evidence {item.id}"
            )

    # -- 9. Empty support on SUPPORTED claim (Req 10.6).
    for claim in claims:
        if str(claim.status) == "SUPPORTED" and not claim.supporting_evidence:
            result.violations.append(
                f"claim {claim.id} marked SUPPORTED with no supporting evidence"
            )

    # -- 10. Overclaim detection (Req 10.4, Property 14).
    for claim in claims:
        if str(claim.status) == "SUPPORTED" and claim.supporting_evidence:
            supporting_items = [e for e in evidence if e.id in claim.supporting_evidence]
            if supporting_items and all(
                e.evidence_type in (EvidenceType.FUNCTIONAL_EQUIVALENT, EvidenceType.THEORETICAL)
                for e in supporting_items
            ):
                result.violations.append(
                    f"claim {claim.id} overclaimed: no direct evidence supports the claim"
                )

    # -- 11. Abstract-only evidence review reason (Req 10.5, Property 15).
    for claim in claims:
        if str(claim.status) == "SUPPORTED" and claim.supporting_evidence:
            supporting_items = [e for e in evidence if e.id in claim.supporting_evidence]
            if supporting_items and all(
                e.reading_depth == ReadingDepth.ABSTRACT_ONLY for e in supporting_items
            ) and not all(
                (source := source_by_id.get(e.source_id)) is not None and inspect_source(source, root)["fully_read"] for e in supporting_items
            ):
                result.review_reasons.append(
                    f"claim {claim.id} supported only by abstract-level evidence"
                )

    # -- 12. Unverified / unretrieved source check (Req 10.7).
    for item in evidence:
        source = source_by_id.get(item.source_id)
        if source is not None:
            is_explicit = (
                "publisher_verified" in source.model_fields_set
                or "retrieval_status" in source.model_fields_set
            )
            if (
                (is_explicit or not is_verified(source.state))
                and not source.publisher_verified
                and source.retrieval_status == RetrievalStatus.NOT_ATTEMPTED
            ):
                result.violations.append(
                    f"evidence {item.id} cites unverified, unretrieved source {item.source_id}"
                )

    # -- 13. Publisher-unverified cited source review reason (Req 4.5, Property 27).
    for source_id in sorted(cited_source_ids):
        source = source_by_id.get(source_id)
        if (
            source is not None
            and "publisher_verified" in source.model_fields_set
            and not source.publisher_verified
        ):
            result.review_reasons.append(
                f"source {source_id} cited in claim but publisher_verified is False"
            )

    # -- 14. Source not indexed review reason (Req 5.4, Property 28).
    for source in sources:
        if "index_status" in source.model_fields_set:
            if not source.index_status or not any(source.index_status.values()):
                result.review_reasons.append(
                    f"source {source.id} not indexed in any queried database"
                )

    return result


def create_review_queue_from_gate_result(
    result: GateResult,
    *,
    claims: list[Claim] | None = None,
    sources: list[Source] | None = None,
) -> ReviewQueue:
    """Convert GateResult review reasons and semantic review claims into ReviewItem records."""
    from src.schemas.claim import ClaimImportance
    from src.schemas.review import ReviewItem, ReviewQueue

    queue = ReviewQueue()
    for reason in result.review_reasons:
        # Determine item_type and item_id if possible
        item_type = "system"
        item_id = "general"
        if "claim " in reason:
            item_type = "claim"
            parts = reason.split("claim ")
            if len(parts) > 1:
                item_id = parts[1].split()[0]
        elif "source " in reason:
            item_type = "source"
            parts = reason.split("source ")
            if len(parts) > 1:
                item_id = parts[1].split()[0]

        queue.add(
            ReviewItem(
                item_type=item_type,
                item_id=item_id,
                severity="MEDIUM",
                reason=reason,
                recommended_action="Investigate and verify before publication",
                status="PENDING",
            )
        )

    # Semantic review claims (Req 13.7, Property 26)
    if claims:
        severity_map = {
            ClaimImportance.CRITICAL: "CRITICAL",
            ClaimImportance.HIGH: "HIGH",
            ClaimImportance.MEDIUM: "MEDIUM",
            ClaimImportance.LOW: "LOW",
        }
        for claim in claims:
            if claim.requires_semantic_review and claim.semantic_review is None:
                sev = severity_map.get(claim.importance, "MEDIUM")
                queue.add(
                    ReviewItem(
                        item_type="claim",
                        item_id=claim.id,
                        severity=sev,
                        reason=f"Claim {claim.id} requires semantic review",
                        recommended_action="Perform semantic review with external evaluator",
                        status="PENDING",
                    )
                )

    return queue
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


def check_document_quality(draft: str, project, reference_list=None, sources=None) -> dict:
    """Only complete literature reviews require the full review topology."""
    sections = []
    parents = []
    for line in draft.splitlines():
        heading = re.match(r"^(#{2,6})\s+(.+)", line.strip())
        if heading:
            level, name = len(heading[1]), canonical_section(heading[2])
            while parents and parents[-1][0] >= level:
                parents.pop()
            parents.append((level, len(sections)))
            sections.append((name, []))
        elif line.strip():
            for _, index in parents:
                sections[index][1].append(line.strip())
    findings = [f"empty section: {name}" for name, content in sections if not content]
    if not draft.strip():
        findings.append("draft is empty")
    required = project.required_sections or (list(SECTION_ALIASES) if project.output_type == "literature_review" else [])
    for name in required:
        if not any(role == canonical_section(name) and content for role, content in sections):
            findings.append(f"required section missing or empty: {name}")
    if reference_list:
        reference_text = "\n".join(line for name, lines in sections if name == "referensi" for line in lines)
        for entry in reference_list.entries:
            if reference_text and entry.formatted not in reference_text:
                findings.append(f"reference list/draft mismatch: {entry.source_id}")
        allowed_lines = {entry.formatted for entry in reference_list.entries}
        allowed_lines.update(entry.formatted + " [sumber belum lengkap]" for entry in reference_list.entries)
        for line in reference_text.splitlines():
            if line.removeprefix("- ") not in allowed_lines:
                findings.append("draft contains a reference absent from the structured reference list")
    reconciliation = None
    if sources is not None and reference_list is not None:
        from src.tools.citation_manager import reconcile_references
        reconciliation = reconcile_references(draft, reference_list, sources)
        findings.extend(reconciliation["findings"])
        for source in sources:
            if source.id not in reconciliation["cited_source_ids"]:
                continue
            if not is_verified(source.state) or not stored_metadata(source):
                findings.append(f"cited source metadata needs re-verification: {source.id}")
            if source.reading_depth == ReadingDepth.FULL_TEXT and not inspect_source(source, project.directory)["fully_read"]:
                findings.append(f"cited FULL_TEXT source lacks examination proof: {source.id}")
    if project.research_options.get("require_free_full_text"):
        used = [s for s in (sources or []) if reconciliation and s.id in reconciliation["cited_source_ids"]]
        if not used:
            findings.append("no cited source satisfies the project free full-text access policy")
        for source in used:
            proof = inspect_source(source, project.directory)
            if not proof["legal_free"] or not proof["scientific_eligible"]:
                findings.append(f"cited source fails scientific/free full-text eligibility: {source.id}")
            if source.metadata.get("version") not in {"version_of_record", "published_version", "accepted_manuscript", "preprint"}:
                findings.append(f"included manuscript version requires verification: {source.id}")
        for heading in ("metode", "keterbatasan"):
            content = "\n".join(line for name, lines in sections if name == heading for line in lines)
            if not any(marker in content.casefold() for marker in ("gratis", "free access", "open access")):
                findings.append("method/limitations must disclose the free full-text access restriction")
    return {"passed": bool(draft.strip()) and not findings, "findings": findings, "output_type": project.output_type, "references": reconciliation}
