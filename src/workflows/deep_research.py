"""End-to-end Deep Research Mode workflow (Bagian A & H).

Specification anchors:
  * AGENT_CONSTITUTION.md §1-30: evidence-based reasoning, anti-fabrication, citation/fact audit.
  * Bagian A: 16-stage end-to-end research flow from raw user request to DOCX or human review.
  * Bagian H: Human review queue for unclear licenses, scan PDFs, conflicting evidence, unsupported claims.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.research import (
    ClaimAgent,
    DiscoveryAgent,
    DiscoveryRequest,
    ResearchPlannerAgent,
    ResearchPlannerRequest,
    RetrievalAgent,
    RetrievalAgentRequest,
    TaskAnalyzerAgent,
    TaskAnalyzerRequest,
    VerificationAgent,
    VerificationRequest,
    rank_sources,
)
from src.core.storage import append_jsonl, write_json
from src.runtime.progress import record_progress
from src.schemas.claim import Claim, ClaimImportance, ClaimStatus, SemanticReview
from src.schemas.evidence import (
    SUPPORTING_RELATIONSHIPS,
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
)
from src.schemas.outline import Outline
from src.schemas.project import Project, ProjectArtifact
from src.schemas.review import ReviewItem, ReviewQueue
from src.schemas.source import AccessMode, RightsStatus, Source, SourceState, is_verified
from src.schemas.task import ResearchMode, Task
from src.tools.crossref import CrossrefTool
from src.tools.dedupe import deduplicate
from src.tools.doab import DOABTool
from src.tools.open_library import OpenLibraryTool
from src.tools.pdf_parser import find_passage_page_location
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.contradiction import detect_contradictions
from src.workflows.evidence_flow import evaluate_claim

__all__ = [
    "DeepResearchRequest",
    "DeepResearchResponse",
    "DeepResearchWorkflow",
    "default_discovery_providers",
]


def default_discovery_providers() -> list[Any]:
    """Default discovery providers combining open-access books (DOAB, Open Library) and journals (Crossref)."""
    return [DOABTool(), OpenLibraryTool(), CrossrefTool()]


class DeepResearchRequest(AgentRequest):
    project: Project
    user_request: str
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None
    providers: list[Any] = Field(default_factory=list)
    semantic_reviews: list[SemanticReview] = Field(default_factory=list)
    verification_engine: Any = None
    generate_docx: bool = True
    min_sources: int = 2
    max_sources: int = 10
    max_retries: int = 3
    command: str = "research"
    input_path: str | None = None


class DeepResearchResponse(AgentResponse):
    plan: dict[str, object] = Field(default_factory=dict)
    stages: list[str] = Field(default_factory=list)
    draft_path: str | None = None
    docx_path: str | None = None
    citation_map_path: str | None = None
    review_queue_path: str | None = None
    review_items: list[dict[str, Any]] = Field(default_factory=list)
    sources_count: int = 0
    claims_count: int = 0
    evidence_count: int = 0
    citation_audit_passed: bool = False
    fact_audit_passed: bool = False


class DeepResearchWorkflow(BaseAgent[DeepResearchRequest, DeepResearchResponse]):
    agent_name = "deep_research_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> DeepResearchResponse:
        return DeepResearchResponse(
            success=False,
            error_message=error_message,
            needs_human_review=bool(extra.get("needs_human_review", False)),
            review_prompt=extra.get("review_prompt") if isinstance(extra.get("review_prompt"), str) else None,
            review_items=extra.get("review_items") if isinstance(extra.get("review_items"), list) else [],
        )

    def _execute(self, request: DeepResearchRequest) -> DeepResearchResponse:
        stages: list[str] = ["deep_plan"]
        review_queue = ReviewQueue()

        # 1. Task Analysis
        record_progress("task_analysis", "running", message=f"Analyzing task: {request.user_request}")
        analyzer_res = TaskAnalyzerAgent().execute(
            TaskAnalyzerRequest(
                user_request=request.user_request,
                workspace=request.project.workspace,
            )
        )
        task = analyzer_res.task or Task(
            user_request=request.user_request,
            mode=ResearchMode.DEEP_RESEARCH,
            workspace=request.project.workspace,
            project_dir=request.project.path,
        )
        task.mode = ResearchMode.DEEP_RESEARCH
        task.project_dir = request.project.path
        keywords = analyzer_res.keywords
        stages.append("task_analysis")
        record_progress("task_analysis", "completed", keywords=keywords)

        # 2. Planning
        record_progress("planning", "running", message="Generating search plan")
        planner_res = ResearchPlannerAgent().execute(
            ResearchPlannerRequest(task=task, keywords=keywords)
        )
        plan = planner_res.plan
        queries = list(plan.get("queries") or [])
        if request.user_request not in queries:
            queries.append(request.user_request)
        plan["queries"] = queries
        plan["mode"] = ResearchMode.DEEP_RESEARCH.value
        stages.append("planning")
        record_progress("planning", "completed", queries=queries)

        # 3. Discovery
        record_progress("discovery", "running", message="Discovering literature across providers")
        if request.sources:
            raw_candidates = list(request.sources)
        else:
            providers = request.providers or default_discovery_providers()
            discovery_res = DiscoveryAgent().execute(
                DiscoveryRequest(
                    candidates=[],
                    queries=queries,
                    providers=providers,
                    max_results_per_query=5,
                )
            )
            raw_candidates = discovery_res.sources
        stages.append("discovery")
        record_progress("discovery", "completed", count=len(raw_candidates))

        # 4. Deduplication
        record_progress("deduplication", "running", message="Deduplicating candidates")
        deduped = deduplicate(raw_candidates)
        cand_path = request.project.artifact_path(ProjectArtifact.CANDIDATES)
        if deduped:
            append_jsonl(cand_path, [s.to_dict() for s in deduped], root=request.project.directory)
        stages.append("deduplication")
        record_progress("deduplication", "completed", unique=len(deduped))

        # 5. Ranking
        record_progress("ranking", "running", message="Ranking candidates by evidence value")
        ranked = rank_sources(deduped)[: request.max_sources]
        stages.append("ranking")
        record_progress("ranking", "completed", ranked=len(ranked))

        # 6. Metadata Verification
        record_progress("verification", "running", message="Verifying bibliographic metadata and DOIs")
        engine = request.verification_engine
        if request.sources:
            # Sources supplied by caller retain their explicit verification state
            verified_sources = ranked
            if engine is not None:
                verif_res = VerificationAgent().execute(
                    VerificationRequest(sources=ranked, engine=engine)
                )
                verified_sources = verif_res.sources
        else:
            engine = engine or VerificationEngine(providers=[])
            verif_res = VerificationAgent().execute(
                VerificationRequest(sources=ranked, engine=engine)
            )
            verified_sources = verif_res.sources
        verif_path = request.project.artifact_path(ProjectArtifact.VERIFIED_SOURCES)
        write_json(verif_path, [s.to_dict() for s in verified_sources], root=request.project.directory, overwrite=True)
        stages.append("verification")
        record_progress("verification", "completed", verified=len(verified_sources))

        # 7. Access / License Classification
        record_progress("access_check", "running", message="Classifying source licensing and download rights")
        for s in verified_sources:
            if s.access_mode == AccessMode.BORROW_ONLY:
                review_queue.add(
                    ReviewItem(
                        item_type="source",
                        item_id=s.id,
                        severity="MEDIUM",
                        reason=f"Source '{s.title}' is borrow-only and cannot be downloaded automatically.",
                        recommended_action="Confirm digital loan or inspect metadata on provider site.",
                    )
                )
            elif s.rights_status == RightsStatus.UNKNOWN and s.download_urls:
                review_queue.add(
                    ReviewItem(
                        item_type="source",
                        item_id=s.id,
                        severity="HIGH",
                        reason=f"Source '{s.title}' has unknown license status for available download URL.",
                        recommended_action="Confirm usage rights from publisher landing page.",
                    )
                )
        stages.append("access_check")
        record_progress("access_check", "completed")

        # 8. Full-Text Retrieval
        record_progress("retrieval", "running", message="Retrieving full-text documents and abstracts")
        retrieval_res = RetrievalAgent().execute(
            RetrievalAgentRequest(project=request.project, sources=verified_sources)
        )
        parsed_text_by_source = retrieval_res.parsed_text_by_source
        for s in verified_sources:
            if any("OCR_REQUIRED" in note for note in s.verification_notes):
                review_queue.add(
                    ReviewItem(
                        item_type="source",
                        item_id=s.id,
                        severity="LOW",
                        reason=f"Downloaded PDF for '{s.title}' is scanned or lacks text layer.",
                        recommended_action="Run OCR on document if verbatim quotes are required.",
                    )
                )
        stages.append("retrieval")
        record_progress("retrieval", "completed", retrieved=len(parsed_text_by_source))

        # 9. Evidence Extraction
        record_progress("evidence_extraction", "running", message="Extracting verbatim evidence")
        evidence_list = list(request.evidence)
        claims_list = list(request.claims)

        # Grounding: If user provided only raw topic without claims/evidence,
        # extract genuine sentences from retrieved text to ground claims
        if not claims_list and parsed_text_by_source:
            for s in verified_sources:
                text = parsed_text_by_source.get(s.id)
                if not text:
                    continue
                clean_text = re.sub(r"<[^>]+>", " ", text)
                clean_text = " ".join(clean_text.split())
                raw_sentences = [
                    sent.strip()
                    for sent in re.split(r"(?<=[.!?])\s+", clean_text)
                    if 35 <= len(sent.strip()) <= 300
                ]
                sentences = [
                    sent for sent in raw_sentences
                    if not any(marker in sent.lower() for marker in ("function (", "function(", "var ", "datalayer", "window.", "document.", "tagname", "{ w[l]", "view of the file"))
                ]
                for sent in sentences[:2]:
                    if s.abstract and sent not in s.abstract and sent in clean_text:
                        s.abstract = clean_text
                    clm_id = f"clm_{len(claims_list) + 1}"
                    evd_id = f"evd_{len(evidence_list) + 1}"
                    pdf_pages = s.metadata.get("pdf_pages") or []
                    loc = find_passage_page_location(sent, pdf_pages) if pdf_pages else None
                    if loc is None:
                        loc = EvidenceLocation(locator="abstract" if s.abstract else "p. 1")

                    ev_item = Evidence(
                        id=evd_id,
                        claim_id=clm_id,
                        source_id=s.id,
                        evidence_text=sent,
                        verbatim=True,
                        quote_verified=True,
                        location=loc,
                        relationship=EvidenceRelationship.SUPPORTS,
                        strength=EvidenceStrength.DEFINITIVE,
                        confidence=1.0,
                    )
                    clm_item = Claim(
                        id=clm_id,
                        claim_text=sent,
                        status=ClaimStatus.SUPPORTED,
                        importance=ClaimImportance.MEDIUM,
                        required_source_count=1,
                        qualifier="berdasarkan temuan literatur awal",
                        supporting_evidence=[evd_id],
                        supporting_sources=[s.id],
                    )
                    evidence_list.append(ev_item)
                    claims_list.append(clm_item)

        stages.append("evidence_extraction")
        record_progress("evidence_extraction", "completed", evidence_count=len(evidence_list))

        # 10. Claim Verification
        record_progress("claim_verification", "running", message="Verifying claim support levels")
        if request.claims:
            evaluated_claims = list(request.claims)
        else:
            evaluated_claims = []
            for clm in claims_list:
                evs = [e for e in evidence_list if e.claim_id == clm.id]
                for ev in evs:
                    if ev.relationship is EvidenceRelationship.CONTRADICTS:
                        clm.attach_contradiction(evidence_id=ev.id, source_id=ev.source_id)
                    elif ev.relationship in SUPPORTING_RELATIONSHIPS:
                        clm.attach_support(evidence_id=ev.id, source_id=ev.source_id)
                eval_res = evaluate_claim(clm, evs)
                clm.support_level = eval_res.support_level
                clm.confidence = eval_res.confidence
                if clm.status != eval_res.status:
                    clm.transition_to(eval_res.status, reason=eval_res.reason, actor="claim_verification")
                if clm.status == ClaimStatus.PARTIALLY_SUPPORTED and not clm.qualifier:
                    clm.qualifier = "berdasarkan temuan literatur awal"
                evaluated_claims.append(clm)
        for clm in evaluated_claims:
            if clm.importance in {ClaimImportance.HIGH, ClaimImportance.CRITICAL} and clm.status in {
                ClaimStatus.INSUFFICIENT_EVIDENCE,
                ClaimStatus.REFUTED,
                ClaimStatus.PROPOSED,
            }:
                review_queue.add(
                    ReviewItem(
                        item_type="claim",
                        item_id=clm.id,
                        severity="HIGH",
                        reason=f"Important claim '{clm.id}' lacks sufficient evidence (status: {clm.status}).",
                        recommended_action="Provide supporting evidence or rephrase claim.",
                    )
                )
        stages.append("claim_verification")
        record_progress("claim_verification", "completed")

        # 11. Contradiction Detection
        record_progress("conflict_detection", "running", message="Detecting contradictory findings")
        for clm in evaluated_claims:
            rep = detect_contradictions(clm, evidence_list)
            if rep.has_mixed_evidence and not clm.qualifier:
                review_queue.add(
                    ReviewItem(
                        item_type="claim",
                        item_id=clm.id,
                        severity="MEDIUM",
                        reason=f"Contradicting evidence detected for claim '{clm.id}' without qualifier.",
                        recommended_action="Add qualifier to claim statement or disclose conflict.",
                    )
                )
        stages.append("conflict_detection")
        record_progress("conflict_detection", "completed")

        # Persist claims.json and evidence.jsonl into project directory
        claims_path = request.project.artifact_path(ProjectArtifact.CLAIMS)
        write_json(claims_path, [c.to_dict() for c in evaluated_claims], root=request.project.directory, overwrite=True)

        evd_path = request.project.artifact_path(ProjectArtifact.EVIDENCE)
        append_jsonl(evd_path, [e.to_dict() for e in evidence_list], root=request.project.directory)

        # Stopping conditions & review queue persistence
        queue_path = request.project.artifact_path(ProjectArtifact.REVIEW_QUEUE)
        review_queue.save(queue_path, root=request.project.directory)

        # Check stopping conditions: minimum sources & critical blocking issues
        valid_sources = [s for s in verified_sources if is_verified(s.state)]
        if len(valid_sources) < request.min_sources and not request.sources:
            review_queue.add(
                ReviewItem(
                    item_type="source",
                    item_id=request.project.id,
                    severity="CRITICAL",
                    reason=f"Found {len(valid_sources)} verified sources, but minimum is {request.min_sources}.",
                    recommended_action="Broaden search query or supply verified sources in input JSON.",
                )
            )
            review_queue.save(queue_path, root=request.project.directory)

        has_critical = any(i.severity == "CRITICAL" for i in review_queue.items)
        if has_critical or not evaluated_claims:
            stages.append("human_review")
            record_progress("human_review", "pending", message="Human review required before draft finalization")
            reasons_text = "\n".join(
                f"{idx + 1}. {i.reason}\n   Action: {i.recommended_action}"
                for idx, i in enumerate(review_queue.items)
            )
            return DeepResearchResponse(
                success=False,
                needs_human_review=True,
                review_prompt=f"Human review required:\n{reasons_text}",
                error_message="Workflow halted: human review required",
                stages=stages,
                plan=plan,
                review_queue_path=str(queue_path),
                review_items=review_queue.to_list(),
                sources_count=len(verified_sources),
                claims_count=len(evaluated_claims),
                evidence_count=len(evidence_list),
            )

        # 12-16. Synthesis, Writing, Citation Audit, Fact Audit, DOCX Generation
        record_progress("synthesis", "running", message="Synthesizing findings")
        record_progress("writing", "running", message="Assembling academic prose and citation map")

        # Load persisted semantic reviews if available in project
        semantic_reviews = list(request.semantic_reviews)
        sem_path = request.project.artifact_path(ProjectArtifact.SEMANTIC_REVIEWS)
        if sem_path.is_file():
            try:
                from src.core.storage import read_json
                raw_sem = read_json(sem_path)
                if isinstance(raw_sem, list):
                    for item in raw_sem:
                        sr = SemanticReview.model_validate(item)
                        if not any(r.claim_id == sr.claim_id for r in semantic_reviews):
                            semantic_reviews.append(sr)
            except Exception:
                pass

        academic = AcademicWritingWorkflow().execute(
            AcademicWritingRequest(
                project=request.project,
                claims=evaluated_claims,
                evidence=evidence_list,
                sources=verified_sources,
                outline=request.outline,
                semantic_reviews=semantic_reviews,
                verification_engine=request.verification_engine,
                generate_docx=request.generate_docx and not any(i.severity in {"CRITICAL", "HIGH"} for i in review_queue.items),
                command=request.command,
                input_path=request.input_path,
            )
        )

        stages.extend(["synthesis", "writing", "citation_audit", "fact_audit"])
        if academic.docx_path:
            stages.append("docx_generation")

        citation_passed = academic.success and "citation_audit" in academic.stages
        fact_passed = academic.success and "fact_audit" in academic.stages

        record_progress("citation_audit", "completed", passed=citation_passed)
        record_progress("fact_audit", "completed", passed=fact_passed)
        if academic.docx_path:
            record_progress("docx_generation", "completed", path=academic.docx_path)

        needs_review = bool(academic.needs_human_review) or len(review_queue.items) > 0 or not academic.success
        if not academic.success and academic.error_message:
            for reason in academic.error_message.split("; "):
                review_queue.add(
                    ReviewItem(
                        item_type="audit",
                        item_id=request.project.id,
                        severity="HIGH",
                        reason=reason,
                        recommended_action="Review and resolve audit findings before final publication",
                    )
                )
            review_queue.save(queue_path, root=request.project.directory)

        if needs_review and "human_review" not in stages:
            stages.append("human_review")
            record_progress("human_review", "pending")

        map_path = request.project.artifact_path(ProjectArtifact.CITATION_MAP)
        reasons_summary = "\n".join(
            f"{idx + 1}. {i.reason}\n   Action: {i.recommended_action}"
            for idx, i in enumerate(review_queue.items)
        )

        return DeepResearchResponse(
            success=academic.success and not has_critical,
            error_message=academic.error_message,
            needs_human_review=needs_review,
            review_prompt=f"Human review required:\n{reasons_summary}" if needs_review and reasons_summary else academic.review_prompt,
            plan=plan,
            stages=stages,
            draft_path=academic.draft_path,
            docx_path=academic.docx_path,
            citation_map_path=str(map_path) if map_path.exists() else None,
            review_queue_path=str(queue_path) if queue_path.exists() else None,
            review_items=review_queue.to_list(),
            sources_count=len(verified_sources),
            claims_count=len(evaluated_claims),
            evidence_count=len(evidence_list),
            citation_audit_passed=citation_passed,
            fact_audit_passed=fact_passed,
        )
