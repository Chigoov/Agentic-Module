"""Academic Writing Mode workflow for roadmap Phase 14 & Phase R4 audit trail."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from src.agents.audit import HumanStyleAuditAgent, HumanStyleAuditRequest
from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.schemas.claim import Claim, ClaimStatus, SemanticReview
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source
from src.tools.docx_generator import DocxGenerationRequest, DocxGenerationTool
from src.tools.quantitative_review_workbook import (
    build_quantitative_review_workbook,
    resolve_standard_workbook_template,
    source_to_review_record,
)
from src.runtime.execution import ensure_workflow_ready, resolve_source_paths
from src.workflows.audit_trail import AcademicRunAudit
from src.workflows.orchestrator import OrchestratorAgent, OrchestratorRequest
from src.workflows.gates import check_document_quality, check_input_references
from src.workflows.evidence_flow import evaluate_claim
from src.core.storage import write_json
from src.schemas.review import ReviewItem, ReviewQueue
from src.tools.source_content import inspect_source

__all__ = ["AcademicWritingRequest", "AcademicWritingResponse", "AcademicWritingWorkflow"]


class AcademicWritingRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None
    generate_docx: bool = True
    command: str | None = "run-academic"
    input_path: str | None = None
    semantic_reviews: list[SemanticReview] = Field(default_factory=list)
    verification_engine: Any = None
    quantitative_review: bool = False
    quantitative_review_records: list[dict[str, Any]] = Field(default_factory=list)
    quantitative_review_template: str | None = None
    quantitative_review_summary: dict[str, Any] = Field(default_factory=dict)
    quantitative_review_request: str = ""
    quantitative_review_exact_count: int | None = None
    quantitative_review_best_count: int | None = None
    require_free_full_text: bool = False


class AcademicWritingResponse(AgentResponse):
    stages: list[str] = Field(default_factory=list)
    draft_path: str | None = None
    docx_path: str | None = None
    run_id: str | None = None
    run_dir: str | None = None
    quantitative_workbook_path: str | None = None
    quantitative_report_path: str | None = None
    checksum_manifest_path: str | None = None


class AcademicWritingWorkflow(BaseAgent[AcademicWritingRequest, AcademicWritingResponse]):
    agent_name = "academic_writing_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> AcademicWritingResponse:
        return AcademicWritingResponse(
            success=False,
            needs_human_review=bool(extra.get("needs_human_review", False)),
            review_prompt=extra.get("review_prompt") if isinstance(extra.get("review_prompt"), str) else None,
            error_message=error_message,
            run_id=extra.get("run_id") if isinstance(extra.get("run_id"), str) else None,
            run_dir=extra.get("run_dir") if isinstance(extra.get("run_dir"), str) else None,
            quantitative_workbook_path=extra.get("quantitative_workbook_path") if isinstance(extra.get("quantitative_workbook_path"), str) else None,
            quantitative_report_path=extra.get("quantitative_report_path") if isinstance(extra.get("quantitative_report_path"), str) else None,
            checksum_manifest_path=extra.get("checksum_manifest_path") if isinstance(extra.get("checksum_manifest_path"), str) else None,
        )

    def _execute(self, request: AcademicWritingRequest) -> AcademicWritingResponse:
        from src.runtime.execution import project_write_lock
        # Preflight precedes even the lockfile or any project output.
        ensure_workflow_ready(project=request.project)
        with project_write_lock(request.project.directory):
            return self._run(request)

    def _run(self, request: AcademicWritingRequest) -> AcademicWritingResponse:
        resolve_source_paths(request.sources, request.project)
        options = review_options(request.model_dump(exclude_unset=True), request.project)
        for name, value in options.items():
            setattr(request, name, value)
        required_tools = [DocxGenerationTool()] if request.generate_docx else []
        required_tools.extend(p for p in getattr(request.verification_engine, "_providers", ())
                              if getattr(p, "is_available", lambda: True)())
        review_template = resolve_standard_workbook_template(request.quantitative_review_template) if request.quantitative_review or request.quantitative_review_records else None
        readiness = ensure_workflow_ready(project=request.project, tools=required_tools)
        write_json(request.project.directory / "workflow_options.json", options, root=request.project.directory, overwrite=True)
        request.project.research_options.update(options)
        write_json(request.project.directory / "project.json", request.project.model_dump(mode="json"), root=request.project.directory, overwrite=True)
        audit = AcademicRunAudit.start(project=request.project, claims=request.claims, evidence=request.evidence,
            sources=request.sources, outline=request.outline, command=request.command or "run-academic", input_path=request.input_path)
        write_json(audit.run_dir / "workflow_options.json", options, root=request.project.directory, overwrite=True)
        search_summary = audit.snapshot_search_summary(request.quantitative_review_summary)
        semantic_reviews = list(request.semantic_reviews)
        sem_path = request.project.artifact_path(ProjectArtifact.SEMANTIC_REVIEWS)
        if sem_path.is_file():
            import json
            for raw in json.loads(sem_path.read_text(encoding="utf-8")):
                item = SemanticReview.model_validate(raw)
                if not any(r.claim_id == item.claim_id for r in semantic_reviews):
                    semantic_reviews.append(item)
        write_json(sem_path, [r.model_dump(mode="json") for r in semantic_reviews], root=request.project.directory, overwrite=True)
        write_json(audit.run_dir / "semantic_reviews.json", [r.model_dump(mode="json") for r in semantic_reviews], root=request.project.directory, overwrite=True)
        quantitative = None
        orchestrated = None
        stages = []
        try:
            original_integrity = check_input_references(claims=request.claims, evidence=request.evidence, sources=request.sources, outline=request.outline)
            withdrawn_ids = {c.id for c in request.claims if c.status == ClaimStatus.WITHDRAWN
                and any(h.to_state == "WITHDRAWN" and h.reason.strip() and h.actor for h in c.history)
                and (not request.outline or c.id not in request.outline.claim_ids)}
            active_integrity = check_input_references(claims=[c for c in request.claims if c.id not in withdrawn_ids],
                evidence=[e for e in request.evidence if e.claim_id not in withdrawn_ids], sources=request.sources, outline=request.outline)
            unresolved_integrity = list(dict.fromkeys(active_integrity.violations + [f for f in original_integrity.violations if f.startswith("duplicate ")]))
            resolved_integrity = [f for f in original_integrity.violations if f not in unresolved_integrity]
            synthesis_sources = request.sources
            source_proofs = {}
            if request.require_free_full_text:
                source_proofs = {s.id: inspect_source(s, request.project.directory) for s in request.sources}
                synthesis_sources = [source for source in request.sources if source_proofs[source.id]["legal_free"] and source_proofs[source.id]["scientific_eligible"]]
                write_json(audit.run_dir / "access_screening.json", [dict(source_id=source.id, included=source in synthesis_sources,
                    version=source.metadata.get("version", "unverified"), proof={k:v for k,v in source_proofs[source.id].items() if k not in {"text", "pages"}}) for source in request.sources], root=request.project.directory, overwrite=True)
            used_ids = {source.id for source in synthesis_sources}
            evidence = [e for e in request.evidence if e.source_id in used_ids]
            evidence_ids = {e.id for e in evidence}
            claims, claim_screening, screening_findings = [], [], list(unresolved_integrity)
            for original in request.claims:
                withdrawn = original.status == ClaimStatus.WITHDRAWN and any(h.to_state == "WITHDRAWN" and h.reason.strip() and h.actor for h in original.history)
                if withdrawn:
                    claim_screening.append(dict(claim_id=original.id, decision="recorded_withdrawal", history=[h.to_dict() for h in original.history], outline_affected=bool(request.outline and original.id in request.outline.claim_ids)))
                    continue
                claim = original.model_copy(deep=True)
                lost_sources = [sid for sid in claim.supporting_sources if sid not in used_ids]
                lost_evidence = [eid for eid in claim.supporting_evidence + claim.contradicting_evidence if eid not in evidence_ids]
                if lost_sources or lost_evidence:
                    claim.supporting_sources = [sid for sid in claim.supporting_sources if sid in used_ids]
                    claim.supporting_evidence = [eid for eid in claim.supporting_evidence if eid in evidence_ids]
                    claim.contradicting_evidence = [eid for eid in claim.contradicting_evidence if eid in evidence_ids]
                    remaining = [e for e in evidence if e.claim_id == claim.id and e.id in claim.supporting_evidence + claim.contradicting_evidence]
                    verdict = evaluate_claim(claim, remaining)
                    if claim.status != verdict.status:
                        claim.transition_to(verdict.status, reason="After source/evidence screening: " + verdict.reason, actor=self.name, support_level=verdict.support_level, confidence=verdict.confidence)
                    else:
                        claim.support_level, claim.confidence = verdict.support_level, verdict.confidence
                    claim.semantic_review = None
                    semantic_reviews = [r for r in semantic_reviews if r.claim_id != claim.id]
                    claim_screening.append(dict(claim_id=claim.id, decision="lost_all_support" if not claim.supporting_evidence else "support_reassessed", removed_source_ids=lost_sources,
                        removed_evidence_ids=lost_evidence, original_status=str(original.status), result_status=str(claim.status), reason=verdict.reason,
                        removed_sources=[{"source_id": sid, "reason": "missing_input" if sid not in {s.id for s in request.sources} else "access_policy" if not source_proofs[sid]["legal_free"] else "scientific_criteria"} for sid in lost_sources],
                        remaining_evidence_ids=claim.supporting_evidence, semantic_review_invalidated=True,
                        outline_affected=bool(request.outline and claim.id in request.outline.claim_ids)))
                    if claim.is_important or lost_evidence and not claim.is_writable or claim.status == ClaimStatus.PARTIALLY_SUPPORTED and not claim.qualifier:
                        screening_findings.append(f"claim {claim.id} lost support during screening; review/revision required: {verdict.reason}")
                claims.append(claim)
            evidence = [e for e in evidence if e.claim_id in {c.id for c in claims}]
            write_json(audit.run_dir / "claim_screening.json", {"input_integrity": original_integrity.violations, "resolved_by_recorded_withdrawal": resolved_integrity, "decisions": claim_screening, "findings": screening_findings}, root=request.project.directory, overwrite=True)
            if screening_findings:
                queue = ReviewQueue.load(request.project.artifact_path(ProjectArtifact.REVIEW_QUEUE))
                for finding in screening_findings:
                    if not any(item.reason == finding and item.status == "PENDING" for item in queue.items):
                        queue.add(ReviewItem(item_type="audit", item_id=request.project.id, severity="HIGH", reason=finding, recommended_action="Repair input or record a claim/outline revision", blocks_finalization=True))
                queue.save(request.project.artifact_path(ProjectArtifact.REVIEW_QUEUE), root=request.project.directory)
            orchestrated = OrchestratorAgent().execute(OrchestratorRequest(project=request.project,
                claims=claims, evidence=evidence, sources=synthesis_sources, outline=request.outline,
                semantic_reviews=semantic_reviews, verification_engine=request.verification_engine))
            write_json(request.project.artifact_path(ProjectArtifact.VERIFIED_SOURCES),
                [source.model_dump(mode="json") for source in request.sources], root=request.project.directory, overwrite=True)
            write_json(audit.run_dir / "verified_sources_snapshot.json",
                [source.model_dump(mode="json") for source in request.sources], root=request.project.directory, overwrite=True)
            stages.extend(orchestrated.stages)
            if review_template:
                records = request.quantitative_review_records or [source_to_review_record(source) for source in request.sources]
                quantitative = build_quantitative_review_workbook(records, audit.run_dir / "review" / "quantitative_review.xlsx",
                    template_path=review_template, summary=search_summary,
                    request_text=request.quantitative_review_request or request.project.user_request,
                    exact_count=request.quantitative_review_exact_count, best_count=request.quantitative_review_best_count,
                    require_free_full_text=request.require_free_full_text).to_dict()
                stages.append("quantitative_review_workbook")
            quality = check_document_quality(orchestrated.draft, request.project, orchestrated.reference_list, synthesis_sources)
            queue = ReviewQueue.load(request.project.artifact_path(ProjectArtifact.REVIEW_QUEUE))
            findings = screening_findings + list(quality["findings"])
            if queue.blocking_items(): findings.append("blocking review items remain unresolved")
            if quantitative and quantitative["status"] != "PASS": findings.append("workbook/scoring is PARTIAL")
            allowed = orchestrated.success and not findings
            if orchestrated.draft:
                style = HumanStyleAuditAgent().execute(HumanStyleAuditRequest(project=request.project, draft=orchestrated.draft, sources=synthesis_sources))
                if not style.success or not style.passed:
                    findings.append(style.error_message or "human style audit requires review")
                    allowed = False
            docx_path = None
            execution_ok = orchestrated.metadata.get("execution_success", True)
            if not execution_ok:
                allowed = False
            error = orchestrated.error_message
            if allowed and request.generate_docx:
                docx = DocxGenerationTool().execute(DocxGenerationRequest(project=request.project, draft=orchestrated.draft,
                    reference_list=orchestrated.reference_list, citation_audit_passed=orchestrated.citation_audit_passed,
                    fact_audit_passed=orchestrated.fact_audit_passed, sources=synthesis_sources,
                    quantitative_workbook_status=quantitative["status"] if quantitative else None))
                stages.append("docx_generation")
                docx_path = docx.docx_path
                if not docx.success:
                    execution_ok = False
                    allowed = False
                    error = docx.error_message
            metadata = {
                "readiness": readiness, "execution_success": execution_ok,
                "result_status": "FAILED" if not execution_ok else ("PASS" if allowed else "PARTIAL"), "finalization_allowed": allowed,
                "needs_human_review": not allowed,
                "human_style_audit_passed": style.passed if orchestrated.draft else False,
                "document_quality": quality, "quantitative_review": quantitative,
                "input_integrity": original_integrity.violations, "resolved_input_integrity": resolved_integrity, "claim_screening": claim_screening,
                "clarification": quantitative["counts"].get("clarification") if quantitative else None,
                "citation_audit_passed": orchestrated.citation_audit_passed, "fact_audit_passed": orchestrated.fact_audit_passed,
                "review_findings": findings, "blocking_review_items": [i.to_dict() for i in queue.blocking_items()],
                "references": {"available": len(request.sources), "assessed": len(synthesis_sources),
                    "synthesis": quality["references"]["cited"] if quality["references"] else 0,
                    "cited": quality["references"]["cited"] if quality["references"] else 0,
                    "written": [entry.model_dump(mode="json") for entry in orchestrated.reference_list.entries] if docx_path and orchestrated.reference_list else [],
                    "draft_entries": [entry.model_dump(mode="json") for entry in orchestrated.reference_list.entries] if orchestrated.reference_list else []},
            }
            # Keep success compatible with the established orchestrator/audit contract.
            success = orchestrated.success and execution_ok
            summary = audit.finish(success=success, stages=stages, draft_path=orchestrated.draft_path, docx_path=docx_path,
                quantitative_workbook_path=quantitative["workbook_path"] if quantitative else None,
                quantitative_report_path=quantitative["report_path"] if quantitative else None,
                checksum_manifest_path=quantitative["manifest_path"] if quantitative else None,
                error_message=error, result_metadata=metadata)
            if quantitative:
                from src.tools.quantitative_review_workbook import update_workflow_report
                update_workflow_report(quantitative, summary)
            return AcademicWritingResponse(success=success, needs_human_review=not allowed,
                review_prompt="; ".join(findings) or orchestrated.review_prompt, error_message=error, stages=stages,
                draft_path=orchestrated.draft_path, docx_path=docx_path, run_id=audit.run_id, run_dir=str(audit.run_dir),
                quantitative_workbook_path=quantitative["workbook_path"] if quantitative else None,
                quantitative_report_path=quantitative["report_path"] if quantitative else None,
                checksum_manifest_path=quantitative["manifest_path"] if quantitative else None, metadata=metadata)
        except Exception as exc:
            metadata = {"execution_success": False, "result_status": "FAILED", "finalization_allowed": False, "needs_human_review": True, "quantitative_review": quantitative}
            paths = dict(quantitative_workbook_path=quantitative["workbook_path"] if quantitative else None,
                quantitative_report_path=quantitative["report_path"] if quantitative else None,
                checksum_manifest_path=quantitative["manifest_path"] if quantitative else None)
            summary = audit.finish(success=False, stages=stages, draft_path=orchestrated.draft_path if orchestrated else None,
                error_message=str(exc), result_metadata=metadata, **paths)
            error = str(exc)
            if quantitative:
                from src.tools.quantitative_review_workbook import update_workflow_report
                try:
                    update_workflow_report(quantitative, summary)
                except (OSError, ValueError) as report_error:
                    error += f"; failed to update report/manifest: {report_error}"
            return AcademicWritingResponse(success=False, error_message=error, needs_human_review=True,
                draft_path=orchestrated.draft_path if orchestrated else None,
                run_id=audit.run_id, run_dir=str(audit.run_dir), stages=stages, metadata=metadata, **paths)


def review_options(payload: dict, project: Project) -> dict:
    """One option contract for CLI, API, resume and finalize."""
    fields = [name for name in AcademicWritingRequest.model_fields if name.startswith("quantitative_review") or name == "require_free_full_text"]
    merged = dict(project.research_options)
    merged.update({name: payload[name] for name in fields if name in payload})
    options = {name: merged[name] for name in fields if name in merged}
    if options.get("quantitative_review_records"):
        options["quantitative_review"] = True
    validated = AcademicWritingRequest(project=project, **options)
    return {name: getattr(validated, name) for name in options}
