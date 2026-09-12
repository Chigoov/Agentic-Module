"""Citation and fact audit agents for roadmap Phase 12."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.storage import backup_file, write_json
from src.schemas.claim import (
    Claim,
    ClaimImportance,
    ClaimStatus,
    SemanticDecision,
    SemanticReview,
    requires_semantic_review,
)
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
    SUPPORTING_RELATIONSHIPS,
)
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source, SourceState, is_verified
from src.tools.citation_manager import (
    detect_internal_tokens,
    detect_orphan_author_year_citations,
    detect_orphan_citations,
)
from src.tools.reference_formatter import citation_key_for, format_reference

__all__ = [
    "CitationAuditRequest",
    "CitationAuditResponse",
    "CitationAuditAgent",
    "FactAuditRequest",
    "FactAuditResponse",
    "FactAuditAgent",
    "STRONG_CLAIM_TERMS",
    "PRELIMINARY_EVIDENCE_TERMS",
    "CAUSAL_OR_EFFECT_TERMS",
]

STRONG_CLAIM_TERMS = (
    "membuktikan",
    "menjamin",
    "menyebabkan",
    "mencegah",
    "melindungi",
    "efektif",
    "meningkatkan secara signifikan",
    "proves",
    "guarantees",
    "causes",
    "prevents",
    "protects",
    "effective",
    "significantly increases",
)

PRELIMINARY_EVIDENCE_TERMS = (
    "observasional",
    "observational",
    "pilot",
    "preliminary",
    "sampel kecil",
    "small sample",
    "korelasional",
    "correlational",
)

CAUSAL_OR_EFFECT_TERMS = (
    "efektif",
    "efektivitas",
    "efek",
    "mekanisme",
    "sebab",
    "menyebabkan",
    "akibat",
    "meningkatkan",
    "menurunkan",
    "causes",
    "effect",
    "mechanism",
    "increases",
    "decreases",
)


def _normalize_text(text: str | None) -> str:
    """Normalize whitespace and case for exact substring comparisons."""
    if not text:
        return ""
    return " ".join(text.casefold().split())


def _locations_contradict(loc_rev: str | None, loc_evd: str | None) -> bool:
    """Check if the semantic review location contradicts the evidence location."""
    if not loc_rev or not loc_evd:
        return False
    r = _normalize_text(loc_rev)
    e = _normalize_text(loc_evd)
    if r in e or e in r:
        return False
    pages_r = set(re.findall(r"\b(?:p|pp|page|halaman)\.?\s*(\d+)", r))
    pages_e = set(re.findall(r"\b(?:p|pp|page|halaman)\.?\s*(\d+)", e))
    if pages_r and pages_e and not (pages_r & pages_e):
        return True
    section_keywords = ("abstract", "introduction", "method", "methods", "result", "results", "discussion", "conclusion")
    sec_r = {s for s in section_keywords if s in r}
    sec_e = {s for s in section_keywords if s in e}
    if sec_r and sec_e and not (sec_r & sec_e):
        return True
    return False


def _check_review_completeness(review: SemanticReview) -> list[str]:
    """Check required fields for SUPPORTED and PARTIALLY_SUPPORTED reviews."""
    missing: list[str] = []
    if not (review.reason and review.reason.strip()):
        missing.append("reason")
    if not (review.evidence_id and review.evidence_id.strip()):
        missing.append("evidence_id")
    if not (review.source_id and review.source_id.strip()):
        missing.append("source_id")
    if not (review.evidence_excerpt and review.evidence_excerpt.strip()):
        missing.append("evidence_excerpt")
    if not (review.location and review.location.strip()):
        missing.append("location")
    if not (review.reviewer and review.reviewer.strip()):
        missing.append("reviewer")
    if not (review.method and review.method.strip()):
        missing.append("method")
    return missing


class CitationAuditRequest(AgentRequest):
    project: Project
    draft: str
    sources: list[Source] = Field(default_factory=list)


class CitationAuditResponse(AgentResponse):
    passed: bool = False
    orphan_citations: list[str] = Field(default_factory=list)
    internal_tokens: list[str] = Field(default_factory=list)
    author_year_orphans: list[str] = Field(default_factory=list)
    audit_path: str | None = None


class CitationAuditAgent(BaseAgent[CitationAuditRequest, CitationAuditResponse]):
    agent_name = "citation_audit_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> CitationAuditResponse:
        return CitationAuditResponse(success=False, error_message=error_message)

    def _execute(self, request: CitationAuditRequest) -> CitationAuditResponse:
        known = {citation_key_for(source) for source in request.sources}
        orphan = detect_orphan_citations(request.draft, known)
        # Audit the citation forms the writer actually emits (audit A02):
        # internal ChatGPT/file tokens and author-year citations whose source
        # is missing from the reference data. Both categories block the audit.
        tokens = detect_internal_tokens(request.draft)
        year_orphans = detect_orphan_author_year_citations(request.draft, request.sources)
        passed = not orphan and not tokens and not year_orphans
        payload = {
            "passed": passed,
            "orphan_citations": orphan,
            "internal_tokens": tokens,
            "author_year_orphans": year_orphans,
        }
        path = request.project.artifact_path(ProjectArtifact.CITATION_AUDIT)
        backup_file(path, root=request.project.directory)
        write_json(path, payload, root=request.project.directory, overwrite=True)
        return CitationAuditResponse(
            passed=passed,
            orphan_citations=orphan,
            internal_tokens=tokens,
            author_year_orphans=year_orphans,
            audit_path=str(path),
        )


class FactAuditRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    semantic_reviews: list[SemanticReview] = Field(default_factory=list)
    verification_engine: Any = None


class FactAuditResponse(AgentResponse):
    passed: bool = False
    structural_passed: bool = False
    semantic_passed: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    assessments: list[dict[str, Any]] = Field(default_factory=list)
    bibliographic_findings: list[dict[str, Any]] = Field(default_factory=list)
    overclaim_findings: list[dict[str, Any]] = Field(default_factory=list)
    verification_reports: list[dict[str, Any]] = Field(default_factory=list)
    audit_path: str | None = None


class FactAuditAgent(BaseAgent[FactAuditRequest, FactAuditResponse]):
    agent_name = "fact_audit_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> FactAuditResponse:
        return FactAuditResponse(
            success=False,
            error_message=error_message,
            passed=False,
            structural_passed=False,
            semantic_passed=False,
            unsupported_claims=extra.get("unsupported_claims") if isinstance(extra.get("unsupported_claims"), list) else [],
            rejection_reasons=[error_message],
        )

    def _execute(self, request: FactAuditRequest) -> FactAuditResponse:
        source_by_id = {s.id: s for s in request.sources}
        evidence_by_id = {e.id: e for e in request.evidence}

        structural_failures: list[str] = []
        unsupported_claims: list[str] = []
        rejection_reasons: list[str] = []
        assessments: list[dict[str, Any]] = []
        bibliographic_findings: list[dict[str, Any]] = []
        overclaim_findings: list[dict[str, Any]] = []
        verification_reports: list[dict[str, Any]] = []

        structural_passed = True
        semantic_passed = True

        # ---------------------------------------------------------------------
        # 1. Reject duplicate semantic reviews for the same claim (Bypass 2)
        # ---------------------------------------------------------------------
        claim_review_counts: dict[str, int] = {}
        for rev in request.semantic_reviews:
            claim_review_counts[rev.claim_id] = claim_review_counts.get(rev.claim_id, 0) + 1
        for claim in request.claims:
            if getattr(claim, "semantic_review", None) is not None:
                claim_review_counts[claim.id] = claim_review_counts.get(claim.id, 0) + 1

        duplicate_claims = {cid for cid, count in claim_review_counts.items() if count > 1}
        reviews_by_claim_id: dict[str, SemanticReview] = {}
        for rev in request.semantic_reviews:
            if rev.claim_id not in duplicate_claims and rev.claim_id not in reviews_by_claim_id:
                reviews_by_claim_id[rev.claim_id] = rev

        for claim in request.claims:
            if (
                getattr(claim, "semantic_review", None)
                and claim.id not in duplicate_claims
                and claim.id not in reviews_by_claim_id
            ):
                reviews_by_claim_id[claim.id] = claim.semantic_review  # type: ignore[assignment]

        if duplicate_claims:
            for cid in sorted(duplicate_claims):
                rejection_reasons.append(
                    f"duplicate semantic reviews detected for claim '{cid}'; multiple reviews rejected"
                )
                structural_failures.append(cid)
                unsupported_claims.append(cid)
            semantic_passed = False

        # ---------------------------------------------------------------------
        # 2. Source verification via VerificationEngine before finalization (Bypass 4)
        # ---------------------------------------------------------------------
        cited_source_ids: set[str] = set()
        for claim in request.claims:
            cited_source_ids.update(claim.supporting_sources)
        for evd in request.evidence:
            cited_source_ids.add(evd.source_id)

        if request.verification_engine is not None:
            for src_id in sorted(cited_source_ids):
                src_obj = source_by_id.get(src_id)
                if not src_obj:
                    continue
                v_res = request.verification_engine.verify(src_obj)
                v_report = v_res.report.to_dict()
                verification_reports.append(v_report)
                if (
                    not is_verified(v_res.recommended_state)
                    or v_res.recommended_state in {SourceState.NEEDS_HUMAN_REVIEW, SourceState.REJECTED}
                ):
                    rejection_reasons.append(
                        f"source '{src_obj.id}' failed provider verification: state={v_res.recommended_state}"
                    )
                    structural_passed = False
                    semantic_passed = False

        # ---------------------------------------------------------------------
        # 3. Bibliographic metadata checks (Tahap 4)
        # ---------------------------------------------------------------------
        for source in request.sources:
            missing_fields: list[str] = []
            if not source.authors:
                missing_fields.append("author")
            if not source.title:
                missing_fields.append("title")
            if source.year is None:
                missing_fields.append("year")
            if not source.venue:
                missing_fields.append("venue")

            ref_entry = format_reference(source)
            if ref_entry.missing_fields:
                missing_fields.extend(f for f in ref_entry.missing_fields if f not in missing_fields)

            if missing_fields:
                bibliographic_findings.append({
                    "source_id": source.id,
                    "missing_fields": missing_fields,
                    "marker": "[sumber belum lengkap]",
                })

        # ---------------------------------------------------------------------
        # 4. Per-claim audit: Structural, Location, Overclaim, and Semantic
        # ---------------------------------------------------------------------
        for claim in request.claims:
            claim_rejections: list[str] = []
            claim_text_lower = claim.claim_text.lower()
            consequential = requires_semantic_review(claim)

            # (A) Structural Writable & Status Check
            if not claim.is_writable:
                structural_failures.append(claim.id)
                claim_rejections.append(f"status '{claim.status}' is not writable")

            if claim.status == ClaimStatus.REFUTED:
                structural_failures.append(claim.id)
                claim_rejections.append("claim status is REFUTED")

            if claim.status == ClaimStatus.PARTIALLY_SUPPORTED and not claim.qualifier:
                structural_failures.append(claim.id)
                claim_rejections.append("partially supported claim cannot pass as full claim without qualifier")

            # (B) Consequential claim mandatory evidence & source (Bypass 3)
            if consequential:
                if not claim.supporting_evidence:
                    structural_failures.append(claim.id)
                    claim_rejections.append("consequential claim has no supporting evidence attached")
                if not claim.supporting_sources:
                    structural_failures.append(claim.id)
                    claim_rejections.append("consequential claim has no supporting sources attached")

            # Validate evidence/source ID referential integrity
            for eid in claim.supporting_evidence:
                if eid not in evidence_by_id:
                    structural_failures.append(claim.id)
                    claim_rejections.append(f"references nonexistent evidence ID '{eid}'")

            for sid in claim.supporting_sources:
                if sid not in source_by_id:
                    structural_failures.append(claim.id)
                    claim_rejections.append(f"references nonexistent source ID '{sid}'")

            # (C) Evidence Provenance & Quote Recomputation for consequential claims
            attached_evds = [evidence_by_id[eid] for eid in claim.supporting_evidence if eid in evidence_by_id]
            if consequential and attached_evds:
                # MODEL_PARAPHRASE cannot be the sole evidence
                has_verbatim = any(
                    e.verbatim is True or e.extraction_method in {ExtractionMethod.VERBATIM_FULLTEXT, ExtractionMethod.VERBATIM_ABSTRACT}
                    for e in attached_evds
                )
                if not has_verbatim:
                    structural_failures.append(claim.id)
                    claim_rejections.append(
                        "MODEL_PARAPHRASE cannot be the sole evidence for consequential claim; verbatim evidence from abstract or full text is required"
                    )

                for evd in attached_evds:
                    if not evd.location.is_precise and not evd.location.locator:
                        structural_failures.append(claim.id)
                        claim_rejections.append(f"evidence '{evd.id}' has unspecified location")

                    src = source_by_id.get(evd.source_id)
                    if src and not is_verified(src.state):
                        structural_failures.append(claim.id)
                        claim_rejections.append(f"source '{src.id}' cited by evidence '{evd.id}' is unverified (state={src.state})")

                    # Recompute quote validity using source abstract or retrieval_path
                    if evd.verbatim or evd.extraction_method in {ExtractionMethod.VERBATIM_FULLTEXT, ExtractionMethod.VERBATIM_ABSTRACT}:
                        source_text = ""
                        if src and src.abstract and src.abstract.strip():
                            source_text = src.abstract
                        elif src and src.retrieval_path and Path(src.retrieval_path).exists():
                            try:
                                source_text = Path(src.retrieval_path).read_text(encoding="utf-8")
                            except Exception:
                                pass

                        if not source_text:
                            claim_rejections.append(
                                f"source text for source '{src.id if src else evd.source_id}' is unavailable to recompute quote validity; requires human review"
                            )
                        else:
                            norm_evd = _normalize_text(evd.evidence_text)
                            norm_src = _normalize_text(source_text)
                            if norm_evd not in norm_src:
                                claim_rejections.append(
                                    f"verbatim evidence '{evd.id}' text is not found in source '{src.id if src else evd.source_id}' abstract/fulltext"
                                )
                            else:
                                evd.quote_verified = True

            # (D) Overclaim Detection (Tahap 5)
            for term in STRONG_CLAIM_TERMS:
                if term in claim_text_lower:
                    is_preliminary = any(
                        any(pt in (e.evidence_text.lower() + " " + (e.notes or "").lower()) for pt in PRELIMINARY_EVIDENCE_TERMS)
                        or e.strength == EvidenceStrength.WEAK
                        for e in attached_evds
                    )
                    if is_preliminary and not claim.qualifier:
                        claim_rejections.append(
                            f"strong claim ('{term}') supported only by preliminary/observational evidence without qualifier"
                        )
                        overclaim_findings.append({
                            "claim_id": claim.id,
                            "term": term,
                            "reason": "preliminary evidence without qualifier",
                        })

            # (E) Semantic Review & Meaning Verification (Tahap 2 & 3, Bypasses 1 & 2)
            review = reviews_by_claim_id.get(claim.id)
            if consequential and not review:
                decision = "NOT_RUN"
                reason = "Klaim konsekuensial belum memiliki rekaman penilaian semantik dari AI agent pemeriksa"
                semantic_status = "NOT_RUN"
                claim_rejections.append("consequential claim has no semantic review record")
                structural_failures.append(claim.id)
            elif review:
                decision = str(review.decision)
                reason = review.reason or ""
                if review.decision in {SemanticDecision.SUPPORTED, SemanticDecision.PARTIALLY_SUPPORTED, "SUPPORTED", "PARTIALLY_SUPPORTED"}:
                    # Bypass 1: Required fields completeness check
                    missing_fields = _check_review_completeness(review)
                    if missing_fields:
                        decision = "NEEDS_HUMAN_REVIEW"
                        semantic_status = "NEEDS_HUMAN_REVIEW"
                        claim_rejections.append(
                            f"semantic review is missing required fields ({', '.join(missing_fields)}) for {review.decision}"
                        )
                    else:
                        # Bypass 2: Chain validation
                        if review.claim_id != claim.id:
                            claim_rejections.append(
                                f"review claim_id '{review.claim_id}' does not match claim '{claim.id}'"
                            )
                        if review.evidence_id not in claim.supporting_evidence:
                            claim_rejections.append(f"review evidence '{review.evidence_id}' is not in claim supporting_evidence")
                        if review.source_id not in claim.supporting_sources:
                            claim_rejections.append(f"review source '{review.source_id}' is not in claim supporting_sources")

                        rev_evd = evidence_by_id.get(review.evidence_id)
                        if not rev_evd:
                            claim_rejections.append(
                                f"review references nonexistent evidence ID '{review.evidence_id}'"
                            )
                        else:
                            if rev_evd.claim_id != claim.id:
                                claim_rejections.append(
                                    f"review evidence '{rev_evd.id}' belongs to claim '{rev_evd.claim_id}', not '{claim.id}'"
                                )
                            if rev_evd.source_id != review.source_id:
                                claim_rejections.append(
                                    f"review evidence '{rev_evd.id}' source '{rev_evd.source_id}' does not match review source '{review.source_id}'"
                                )

                            # Location contradiction check
                            if _locations_contradict(review.location, rev_evd.location.describe()):
                                claim_rejections.append(
                                    f"review location '{review.location}' contradicts evidence location '{rev_evd.location.describe()}'"
                                )

                            # Bypass 2: Exact contiguous substring check
                            norm_excerpt = _normalize_text(review.evidence_excerpt)
                            norm_evd_text = _normalize_text(rev_evd.evidence_text)
                            if not norm_excerpt:
                                claim_rejections.append("review evidence_excerpt is empty")
                            elif norm_excerpt not in norm_evd_text:
                                claim_rejections.append(
                                    f"review evidence_excerpt is not an exact substring of evidence '{rev_evd.id}' text"
                                )

                        if review.decision in {SemanticDecision.PARTIALLY_SUPPORTED, "PARTIALLY_SUPPORTED"}:
                            if not claim.qualifier:
                                semantic_status = "PARTIALLY_SUPPORTED_UNQUALIFIED"
                                claim_rejections.append("claim is only partially supported and cannot pass as full claim without qualifier")
                            else:
                                semantic_status = "SUPPORTED_WITH_QUALIFIER" if not claim_rejections else "FAILED"
                        else:
                            semantic_status = "PASSED" if not claim_rejections else "FAILED"

                elif review.decision in {SemanticDecision.REFUTED, "REFUTED"}:
                    semantic_status = "REFUTED"
                    claim_rejections.append(f"claim is REFUTED by semantic review: {reason}")
                elif review.decision in {SemanticDecision.NEEDS_HUMAN_REVIEW, SemanticDecision.NOT_RUN, "NEEDS_HUMAN_REVIEW", "NOT_RUN"}:
                    semantic_status = "NEEDS_HUMAN_REVIEW"
                    claim_rejections.append(f"claim requires human review: {reason}")
                else:
                    semantic_status = "UNKNOWN_DECISION"
                    claim_rejections.append(f"unknown semantic review decision '{decision}'")
            else:
                # Ordinary non-consequential claim with no review
                decision = "SUPPORTED"
                reason = "Supporting statement"
                semantic_status = "PASSED" if not claim_rejections else "FAILED"

            if claim.id in structural_failures or (not claim.is_writable):
                structural_passed = False
                unsupported_claims.append(claim.id)

            if claim_rejections:
                rejection_reasons.extend([f"claim {claim.id}: {r}" for r in claim_rejections])
                semantic_passed = False
                if claim.id not in unsupported_claims:
                    unsupported_claims.append(claim.id)

            first_eid = (
                claim.supporting_evidence[0]
                if claim.supporting_evidence
                else (review.evidence_id if review else None)
            )
            first_evd = evidence_by_id.get(first_eid) if first_eid else None
            first_sid = (
                claim.supporting_sources[0]
                if claim.supporting_sources
                else (review.source_id if review else None)
            )

            assessments.append({
                "claim_id": claim.id,
                "claim_text": claim.claim_text,
                "importance": (
                    claim.importance.name
                    if hasattr(claim.importance, "name")
                    else str(claim.importance)
                ),
                "structural_status": "FAILED" if (claim.id in structural_failures) else "PASSED",
                "semantic_status": semantic_status,
                "decision": decision,
                "reason": reason,
                "evidence_id": first_eid,
                "evidence_text": first_evd.evidence_text if first_evd else (review.evidence_excerpt if review else None),
                "evidence_location": (
                    first_evd.location.describe()
                    if first_evd
                    else (review.location if review else None)
                ),
                "source_id": first_sid,
                "reviewer": review.reviewer if review else None,
                "method": review.method if review else None,
                "timestamp": review.timestamp if review else None,
                "rejection_reasons": claim_rejections,
            })

        # Overall passed logic (Tahap 3):
        # Only true if both structural_passed and semantic_passed pass,
        # and no claims are unsupported or rejected.
        passed = (
            structural_passed
            and semantic_passed
            and not unsupported_claims
            and not rejection_reasons
        )

        payload = {
            "passed": passed,
            "structural_passed": structural_passed,
            "semantic_passed": semantic_passed,
            "unsupported_claims": sorted(list(set(unsupported_claims))),
            "rejection_reasons": rejection_reasons,
            "assessments": assessments,
            "bibliographic_findings": bibliographic_findings,
            "overclaim_findings": overclaim_findings,
            "verification_reports": verification_reports,
        }
        path = request.project.artifact_path(ProjectArtifact.FACT_AUDIT)
        backup_file(path, root=request.project.directory)
        write_json(path, payload, root=request.project.directory, overwrite=True)

        return FactAuditResponse(
            passed=passed,
            structural_passed=structural_passed,
            semantic_passed=semantic_passed,
            unsupported_claims=sorted(list(set(unsupported_claims))),
            rejection_reasons=rejection_reasons,
            assessments=assessments,
            bibliographic_findings=bibliographic_findings,
            overclaim_findings=overclaim_findings,
            verification_reports=verification_reports,
            audit_path=str(path),
        )
