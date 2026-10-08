"""End-to-end unit tests for the research pipeline (Bagian A, H, and I)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conftest import fixture_source

from src.core.storage import read_jsonl
from src.runtime.cli import main
from src.runtime.progress import read_progress
from src.schemas.claim import Claim, ClaimImportance, ClaimStatus
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
    ReadingDepth,
)
from src.schemas.project import Project, ProjectArtifact
from src.schemas.review import ReviewQueue
from src.schemas.source import AccessMode, RightsStatus, Source, SourceState, SourceType
from src.tools.research_tool import ResearchRequest, ResearchResponse, ResearchTool
from src.workflows.deep_research import DeepResearchRequest, DeepResearchResponse, DeepResearchWorkflow


def _make_project(tmp_path: Path, name: str = "deep_res_proj") -> Project:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return Project(name=name, workspace="tmp", path=str(p), title="Deep Research")


class MockBookProvider(ResearchTool):
    origin = "mock_provider"
    tool_name = "mock_provider"
    _integration_verified = False

    def __init__(self, sample_sources: list[Source]) -> None:
        super().__init__()
        self._sample_sources = sample_sources

    def _search(self, request: ResearchRequest) -> tuple[list[Source], int, str, str]:
        return list(self._sample_sources), len(self._sample_sources), "https://mock.test/api", "{}"


def test_research_pipeline_end_to_end_from_raw_topic(tmp_path: Path) -> None:
    project = _make_project(tmp_path, "ocean_plastic_proj")
    project.output_type = "literature_review"

    s1 = Source(
        id="src_b1",
        title="Microplastics in Pelagic Waters",
        authors=["Thompson, R.", "Galloway, T."],
        year=2023,
        venue="Marine Ecology Press",
        doi="10.1016/j.mep.2023.01",
        landing_url="https://example.test/book1",
        download_urls=["https://example.test/book1.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
        state=SourceState.APPROVED,
        abstract="Microplastics accumulate significantly in coastal pelagic ecosystems and affect marine fauna.",
    )
    s2 = Source(
        id="src_b2",
        title="Ecotoxicology of Synthetic Fibers",
        authors=["Thompson, R.", "Cole, M."],
        year=2023,
        venue="Oceanic Academic",
        doi="10.1016/j.oa.2023.02",
        landing_url="https://example.test/book2",
        download_urls=["https://example.test/book2.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
        state=SourceState.APPROVED,
        abstract="Synthetic microfibers disrupt digestion and reproductive health in filter-feeding organisms.",
    )

    fixture_source(s1, root=project.directory / "source_documents", cache_report=True)
    fixture_source(s2, root=project.directory / "source_documents", cache_report=True)
    provider = MockBookProvider([s1, s2])

    workflow = DeepResearchWorkflow()
    response = workflow.execute(
        DeepResearchRequest(
            project=project,
            user_request="Microplastics impact on marine ecosystems",
            providers=[provider],
            generate_docx=True,
        )
    )

    assert response.success is True
    assert response.draft_path is not None
    assert Path(response.draft_path).is_file()
    assert response.docx_path is None
    assert response.metadata["finalization_allowed"] is False
    assert response.metadata["result_status"] == "PARTIAL"

    # Verify stages executed
    expected_stages = [
        "deep_plan",
        "task_analysis",
        "planning",
        "discovery",
        "deduplication",
        "ranking",
        "verification",
        "access_check",
        "retrieval",
        "evidence_extraction",
        "claim_verification",
        "conflict_detection",
        "synthesis",
        "writing",
        "citation_audit",
        "fact_audit",
    ]
    for stg in expected_stages:
        assert stg in response.stages

    # Verify citation map artifact
    assert response.citation_map_path is not None
    map_data = json.loads(Path(response.citation_map_path).read_text(encoding="utf-8"))
    assert "citations" in map_data
    assert len(map_data["citations"]) >= 1

    # Verify disambiguated citation labels
    draft_content = Path(response.draft_path).read_text(encoding="utf-8")
    assert "Thompson" in draft_content

    # Check progress logging was performed
    prog = read_progress()
    stages_logged = {p["stage"] for p in prog}
    assert "task_analysis" in stages_logged
    assert "discovery" in stages_logged
    assert "retrieval" in stages_logged
    assert "writing" in stages_logged


def test_research_pipeline_halts_on_critical_human_review(tmp_path: Path) -> None:
    project = _make_project(tmp_path, "halted_proj")

    # Only 1 unverified source found, but min_sources is 2
    s_unverified = Source(
        id="src_unv",
        title="Unverified Preprint",
        authors=["Anonymous, X."],
        year=2024,
        state=SourceState.DISCOVERED,
        download_urls=["https://unknown.test/file.pdf"],
        access_mode=AccessMode.UNKNOWN,
        rights_status=RightsStatus.UNKNOWN,
        abstract="Uncorroborated preliminary text without verified metadata.",
    )
    provider = MockBookProvider([s_unverified])

    workflow = DeepResearchWorkflow()
    response = workflow.execute(
        DeepResearchRequest(
            project=project,
            user_request="Unverified study inquiry",
            providers=[provider],
            min_sources=2,
            generate_docx=True,
        )
    )

    # Workflow must halt for human review, not fabricating a DOCX
    assert response.success is False
    assert response.needs_human_review is True
    assert "human_review" in response.stages
    assert response.docx_path is None
    assert response.review_queue_path is not None

    # Review queue artifact persists actionable items
    queue_file = Path(response.review_queue_path)
    assert queue_file.is_file()
    items = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(items) >= 1
    assert any("Action:" in response.review_prompt for item in items)


def test_research_pipeline_preserves_conflicting_sources(tmp_path: Path) -> None:
    project = _make_project(tmp_path, "conflict_proj")

    s1 = Source(
        id="src_pro",
        title="Benefit Study",
        authors=["Pro, A."],
        year=2023,
        state=SourceState.APPROVED,
        abstract="The treatment is safe and effective.",
    )
    s2 = Source(
        id="src_con",
        title="Risk Study",
        authors=["Con, B."],
        year=2023,
        state=SourceState.APPROVED,
        abstract="The treatment shows significant side effects.",
    )

    ev1 = Evidence(
        id="ev_pro",
        claim_id="clm_1",
        source_id="src_pro",
        evidence_text="The treatment is safe and effective.",
        verbatim=True,
        quote_verified=True,
        location=EvidenceLocation(page=1),
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    ev2 = Evidence(
        id="ev_con",
        claim_id="clm_1",
        source_id="src_con",
        evidence_text="The treatment shows significant side effects.",
        verbatim=True,
        quote_verified=True,
        location=EvidenceLocation(page=1),
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.STRONG,
    )

    claim = Claim(
        id="clm_1",
        claim_text="Treatment has benefits though risks were also observed.",
        qualifier="evidence is mixed across studies",
        status=ClaimStatus.CONFLICTED,
        importance=ClaimImportance.MEDIUM,
        supporting_evidence=["ev_pro"],
        supporting_sources=["src_pro", "src_con"],
        contradicting_evidence=["ev_con"],
    )

    fixture_source(s1)
    fixture_source(s2)
    for ev in (ev1, ev2):
        ev.extraction_method = ExtractionMethod.VERBATIM_ABSTRACT
        ev.location = EvidenceLocation(locator="abstract")
    response = DeepResearchWorkflow().execute(
        DeepResearchRequest(
            project=project,
            user_request="Treatment safety and efficacy",
            claims=[claim],
            evidence=[ev1, ev2],
            sources=[s1, s2],
            generate_docx=True,
        )
    )

    assert response.success is True
    # Contradicting source is NOT removed
    draft = Path(response.draft_path).read_text(encoding="utf-8")
    assert "Pro, 2023" in draft
    assert "Con, 2023" in draft
    assert "(evidence is mixed across studies)" in draft


def test_cli_research_command_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Test that `python -m src research --topic ...` is invoked cleanly
    cmd_args = ["research", "--topic", "Climate impact on coral reefs", "--no-docx"]

    s1 = Source(
        id="src_coral",
        title="Coral Bleaching Trends",
        authors=["Hughes, T."],
        year=2022,
        state=SourceState.APPROVED,
        abstract="Elevated ocean temperatures accelerate widespread bleaching events.",
    )
    # Mock providers inside DeepResearchWorkflow to avoid internet dependency
    def mock_execute(self, request):
        return DeepResearchResponse(
            success=True,
            stages=["task_analysis", "discovery", "writing", "citation_audit", "fact_audit"],
            draft_path=str(tmp_path / "draft.md"),
            sources_count=1,
            claims_count=1,
            evidence_count=1,
            citation_audit_passed=True,
            fact_audit_passed=True,
        )

    monkeypatch.setattr(DeepResearchWorkflow, "execute", mock_execute)

    exit_code = main(cmd_args)
    assert exit_code == 0


def test_default_discovery_providers_configuration() -> None:
    """Validate default discovery providers configuration, types, and sequential ordering.

    Validates: Requirements 3.1, 3.4
    """
    from src.tools.crossref import CrossrefTool
    from src.tools.doab import DOABTool
    from src.tools.open_library import OpenLibraryTool
    from src.workflows.deep_research import default_discovery_providers

    providers = default_discovery_providers()
    provider_types = [type(p) for p in providers]

    assert provider_types == [DOABTool, OpenLibraryTool, CrossrefTool]
    assert DOABTool in provider_types
    assert OpenLibraryTool in provider_types
    assert CrossrefTool in provider_types
    assert len(providers) == 3


def test_workflow_uses_default_discovery_providers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate DeepResearchWorkflow queries default discovery providers when request.providers is omitted.

    Validates: Requirements 3.2, 3.3, 3.4
    """
    from src.tools.crossref import CrossrefTool
    from src.tools.doab import DOABTool
    from src.tools.open_library import OpenLibraryTool

    project = _make_project(tmp_path, "default_prov_proj")
    executed_providers = []

    def mock_discovery_execute(self, req):
        executed_providers.extend(type(p) for p in req.providers)
        # return dummy candidate to allow workflow to proceed cleanly
        s = Source(
            id="s_dummy",
            title="Dummy Book",
            authors=["Author, D."],
            year=2023,
            state=SourceState.APPROVED,
            abstract="Dummy abstract text.",
        )
        return DiscoveryResponse(sources=[s], metadata={})

    from src.agents.research import DiscoveryAgent, DiscoveryResponse

    monkeypatch.setattr(DiscoveryAgent, "execute", mock_discovery_execute)

    workflow = DeepResearchWorkflow()
    # Execute without custom providers (request.providers omitted)
    workflow.execute(
        DeepResearchRequest(
            project=project,
            user_request="Test topic for providers",
            min_sources=1,
            generate_docx=False,
        )
    )

    assert executed_providers == [DOABTool, OpenLibraryTool, CrossrefTool]
    assert DOABTool in executed_providers
    assert OpenLibraryTool in executed_providers
    assert CrossrefTool in executed_providers


def test_artifact_store_persistence_and_run_directory_structure(tmp_path: Path) -> None:
    """Verify artifact store persistence and run directory structure during research workflow execution.

    Validates: Requirements 4.2
    - Verify persistence of candidates.jsonl containing raw search results
    - Verify persistence of verified_sources.json containing validated bibliographic records
    - Verify storage of retrieved files under source_documents/
    - Verify immutable snapshot creation under runs/<run_id>/
    """
    project = _make_project(tmp_path, "artifact_store_test_proj")

    s1 = Source(
        id="src_art1",
        title="Community-Based Forest Adaptation Strategies",
        authors=["Rahman, A.", "Santoso, B."],
        year=2023,
        venue="Forestry and Climate Journal",
        doi="10.1016/j.fcj.2023.05",
        landing_url="https://example.test/book1",
        download_urls=["https://example.test/book1.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
        state=SourceState.APPROVED,
        abstract="Community-based forest management significantly enhances local adaptive capacity and food security against climate shocks.",
    )
    s2 = Source(
        id="src_art2",
        title="Agroforestry and Household Food Security Resilience",
        authors=["Wahyuni, S.", "Pratama, D."],
        year=2023,
        venue="Agricultural Resilience Press",
        doi="10.1016/j.arp.2023.08",
        landing_url="https://example.test/book2",
        download_urls=["https://example.test/book2.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
        state=SourceState.APPROVED,
        abstract="Agroforestry diversification provides supplemental food reserves and buffers microclimate extremes during severe droughts.",
    )

    fixture_source(s1, root=project.directory / "source_documents", cache_report=True)
    fixture_source(s2, root=project.directory / "source_documents", cache_report=True)
    provider = MockBookProvider([s1, s2])
    workflow = DeepResearchWorkflow()
    response = workflow.execute(
        DeepResearchRequest(
            project=project,
            user_request="Strategi adaptasi berbasis komunitas dan ketahanan pangan",
            providers=[provider],
            min_sources=2,
            generate_docx=False,
        )
    )

    assert response.success is True

    # 1. Verify persistence of candidates.jsonl containing raw search results
    cand_path = project.artifact_path(ProjectArtifact.CANDIDATES)
    assert cand_path.is_file(), f"Expected candidates.jsonl at {cand_path}"
    candidates = read_jsonl(cand_path)
    assert len(candidates) >= 2
    cand_ids = {c["id"] for c in candidates}
    assert "src_art1" in cand_ids
    assert "src_art2" in cand_ids
    assert any(c.get("title") == "Community-Based Forest Adaptation Strategies" for c in candidates)
    assert any(c.get("title") == "Agroforestry and Household Food Security Resilience" for c in candidates)

    # 2. Verify persistence of verified_sources.json containing validated bibliographic records
    verif_path = project.artifact_path(ProjectArtifact.VERIFIED_SOURCES)
    assert verif_path.is_file(), f"Expected verified_sources.json at {verif_path}"
    verified_data = json.loads(verif_path.read_text(encoding="utf-8"))
    assert len(verified_data) >= 2
    verif_ids = {s["id"] for s in verified_data}
    assert "src_art1" in verif_ids
    assert "src_art2" in verif_ids
    assert all(s.get("doi") for s in verified_data)

    # 3. Verify storage of retrieved files under source_documents/
    docs_dir = project.directory / "source_documents"
    assert docs_dir.is_dir(), f"Expected source_documents directory at {docs_dir}"
    retrieved_files = list(docs_dir.iterdir())
    assert len(retrieved_files) >= 1, "Expected at least one retrieved document file under source_documents/"
    assert all(f.stat().st_size > 0 for f in retrieved_files), "Retrieved files must be non-empty"

    # 4. Verify immutable snapshot creation under runs/<run_id>/
    runs_dir = project.directory / "runs"
    assert runs_dir.is_dir(), f"Expected runs directory at {runs_dir}"
    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    assert len(run_dirs) >= 1, "Expected at least one run snapshot directory under runs/"

    active_run = run_dirs[0]
    expected_snapshots = [
        "input_snapshot.json",
        "sources_snapshot.json",
        "claims_snapshot.json",
        "evidence_snapshot.json",
        "outline_snapshot.json",
        "citation_audit_snapshot.json",
        "fact_audit_snapshot.json",
        "run_summary.json",
    ]
    for snapshot_name in expected_snapshots:
        snapshot_file = active_run / snapshot_name
        assert snapshot_file.is_file(), f"Expected snapshot file {snapshot_name} in {active_run}"
        # Ensure file parses as valid JSON (dict, list, or null for optional outline)
        parsed_snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
        if snapshot_name in {"input_snapshot.json", "run_summary.json", "citation_audit_snapshot.json", "fact_audit_snapshot.json"}:
            assert isinstance(parsed_snapshot, dict)
        elif snapshot_name in {"sources_snapshot.json", "claims_snapshot.json", "evidence_snapshot.json"}:
            assert isinstance(parsed_snapshot, list)

    # Validate run_summary.json structure and contents
    summary_data = json.loads((active_run / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_data["run_id"] == active_run.name
    assert summary_data["started_at"] is not None
    assert summary_data["command"] == "research"
    assert "stages" in summary_data
    assert "writing" in summary_data["stages"]
    assert "citation_audit" in summary_data["stages"]
    assert "fact_audit" in summary_data["stages"]


def test_cli_deep_research_persisted_artifacts_integrity() -> None:
    """Verify persisted artifact integrity of the real CLI deep research run on climate adaptation.

    Validates: Requirements 4.2
    - candidates.jsonl contains raw search results
    - verified_sources.json contains validated bibliographic records
    - source_documents/ contains retrieved document files
    - runs/<run_id>/ contains immutable run snapshots and run_summary.json
    """
    from src.core.paths import get_paths

    proj_dir = get_paths().workspace_path("TUGAS 1") / "dampak_perubahan_iklim_terhada"
    if not proj_dir.is_dir():
        pytest.skip("Project directory TUGAS 1/dampak_perubahan_iklim_terhada not present")

    # 1. candidates.jsonl
    cand_file = proj_dir / "candidates.jsonl"
    assert cand_file.is_file()
    assert cand_file.stat().st_size > 0
    cand_records = read_jsonl(cand_file)
    assert len(cand_records) >= 2
    for record in cand_records:
        assert "id" in record
        assert "title" in record
        assert "provenance" in record

    # 2. verified_sources.json
    verif_file = proj_dir / "verified_sources.json"
    assert verif_file.is_file()
    assert verif_file.stat().st_size > 0
    verif_records = json.loads(verif_file.read_text(encoding="utf-8"))
    assert len(verif_records) >= 2
    for record in verif_records:
        assert "id" in record
        assert "title" in record
        assert "doi" in record
        assert record.get("state") in {"DOI_VERIFIED", "VERIFIED", "APPROVED", "DISCOVERED"}

    # 3. source_documents/
    docs_dir = proj_dir / "source_documents"
    assert docs_dir.is_dir()
    doc_files = [f for f in docs_dir.iterdir() if f.is_file()]
    assert len(doc_files) >= 1
    assert all(f.stat().st_size > 0 for f in doc_files)

    # 4. runs/<run_id>/
    runs_dir = proj_dir / "runs"
    assert runs_dir.is_dir()
    run_folders = [d for d in runs_dir.iterdir() if d.is_dir()]
    assert len(run_folders) >= 1

    latest_run = sorted(run_folders, key=lambda p: p.name)[-1]
    expected_snapshots = [
        "input_snapshot.json",
        "sources_snapshot.json",
        "claims_snapshot.json",
        "evidence_snapshot.json",
        "outline_snapshot.json",
        "citation_audit_snapshot.json",
        "fact_audit_snapshot.json",
        "run_summary.json",
    ]
    for snap in expected_snapshots:
        snap_path = latest_run / snap
        assert snap_path.is_file(), f"Missing snapshot {snap} in {latest_run}"
        # Ensure file parses as valid JSON (dict, list, or null for optional outline)
        content = json.loads(snap_path.read_text(encoding="utf-8"))
        if snap in {"input_snapshot.json", "run_summary.json", "citation_audit_snapshot.json", "fact_audit_snapshot.json"}:
            assert isinstance(content, dict)
        elif snap in {"sources_snapshot.json", "claims_snapshot.json", "evidence_snapshot.json"}:
            assert isinstance(content, list)

    summary = json.loads((latest_run / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == latest_run.name
    assert summary["started_at"] is not None
    assert summary["command"] == "research"


def test_property_6_citation_audit_integrity_and_token_hygiene(tmp_path: Path) -> None:
    """Feature: policy-safe-live-verification, Property 6: Citation Audit Integrity and Token Hygiene.

    For any research synthesis output, every citation token in draft.md SHALL resolve to an
    approved source in citation_map.json, and the document SHALL contain zero unverified orphan
    citations, zero fabricated DOIs, and zero internal LLM tokens (turn, view, search, filecite).

    Validates: Requirements 4.3, 4.4
    """
    from src.agents.audit import CitationAuditAgent, CitationAuditRequest
    from src.tools.citation_manager import (
        detect_internal_tokens,
        detect_orphan_citations,
        detect_orphan_author_year_citations,
    )

    project = _make_project(tmp_path, "prop6_proj")

    s1 = Source(
        id="src_prop6_1",
        title="Valid Climate Impact Study",
        authors=["Suryani, A."],
        year=2023,
        doi="10.1016/j.jclepro.2023.1001",
        state=SourceState.APPROVED,
    )
    s2 = Source(
        id="src_prop6_2",
        title="Food Security Adaptations",
        authors=["Pranata, B."],
        year=2024,
        doi="10.1016/j.gloenvcha.2024.1002",
        state=SourceState.APPROVED,
    )

    # 1. Clean draft with valid APA 7 in-text citations and complete bibliography
    clean_draft = (
        "# Clean Synthesis\n\n"
        "Perubahan iklim mempengaruhi ketahanan pangan (Suryani, 2023).\n\n"
        "> \"Strategi adaptasi meningkatkan stabilitas hasil panen.\" (Pranata, 2024, p. 12)\n\n"
        "## References\n\n"
        "- Suryani, A. (2023). Valid Climate Impact Study. Journal of Cleaner Production. https://doi.org/10.1016/j.jclepro.2023.1001\n"
        "- Pranata, B. (2024). Food Security Adaptations. Global Environmental Change. https://doi.org/10.1016/j.gloenvcha.2024.1002\n"
    )

    audit_agent = CitationAuditAgent()
    resp_clean = audit_agent.execute(
        CitationAuditRequest(project=project, draft=clean_draft, sources=[s1, s2])
    )
    assert resp_clean.passed is True
    assert resp_clean.orphan_citations == []
    assert resp_clean.internal_tokens == []
    assert resp_clean.author_year_orphans == []

    # 2. Contaminated drafts with internal LLM tokens must be rejected
    contaminated_tokens = [
        "Perubahan iklim turn1 menyebabkan kekeringan.",
        "Data adaptasi view2 menunjukkan perbaikan.",
        "Temuan search3 mengonfirmasi korelasi.",
        "Kutipan filecite membuktikan hasil.",
        "Kutipan citeturn valid.",
    ]
    for bad_text in contaminated_tokens:
        found_tokens = detect_internal_tokens(bad_text)
        assert len(found_tokens) > 0
        resp_bad = audit_agent.execute(
            CitationAuditRequest(project=project, draft=bad_text, sources=[s1, s2])
        )
        assert resp_bad.passed is False
        assert len(resp_bad.internal_tokens) > 0

    # 3. Draft with orphan citation key or unverified author-year must be rejected
    orphan_draft = "Studi independen (Unknown, 2021) menyatakan hal berbeda."
    resp_orphan = audit_agent.execute(
        CitationAuditRequest(project=project, draft=orphan_draft, sources=[s1, s2])
    )
    assert resp_orphan.passed is False
    assert len(resp_orphan.author_year_orphans) > 0


def test_audit_generated_draft_citations_and_token_hygiene() -> None:
    """Audit generated draft citations and token hygiene from real CLI research run.

    - Audit draft.md for APA 7 in-text citation formatting and complete bibliography entries
    - Verify citation_map.json maintains bidirectional links between citations, sources, claims, and evidence
    - Audit citation_audit.json to guarantee zero internal LLM tokens (turn, view, search, filecite),
      zero orphan markers, and zero fabricated DOIs
    Validates: Requirements 4.3, 4.4
    """
    import re
    from src.core.paths import get_paths
    from src.tools.citation_manager import (
        detect_internal_tokens,
        detect_orphan_citations,
        detect_orphan_author_year_citations,
        citation_key_for,
    )

    proj_dir = get_paths().workspace_path("TUGAS 1") / "dampak_perubahan_iklim_terhada"
    if not proj_dir.is_dir():
        pytest.skip("Project directory TUGAS 1/dampak_perubahan_iklim_terhada not present")

    draft_file = proj_dir / "draft.md"
    citation_map_file = proj_dir / "citation_map.json"
    citation_audit_file = proj_dir / "citation_audit.json"
    verified_sources_file = proj_dir / "verified_sources.json"
    claims_file = proj_dir / "claims.json"
    evidence_file = proj_dir / "evidence.jsonl"

    assert draft_file.is_file(), "draft.md must exist"
    assert citation_map_file.is_file(), "citation_map.json must exist"
    assert citation_audit_file.is_file(), "citation_audit.json must exist"
    assert verified_sources_file.is_file(), "verified_sources.json must exist"
    assert claims_file.is_file(), "claims.json must exist"
    assert evidence_file.is_file(), "evidence.jsonl must exist"

    # 1. Audit draft.md
    draft_text = draft_file.read_text(encoding="utf-8")
    assert len(draft_text) > 0, "draft.md must not be empty"
    assert "## References" in draft_text, "draft.md must contain ## References section"

    parts = draft_text.split("## References")
    body_text = parts[0]
    refs_text = parts[1]

    # Check APA 7 in-text citations in body
    in_text_pattern = re.compile(r"\(([A-Z][a-zA-Z\s\.\,\'\&-]+?),\s*(\d{4}[a-z]?)(?:,\s*([^)]+))?\)")
    found_citations = in_text_pattern.findall(body_text)
    assert len(found_citations) >= 4, "Must find at least 4 in-text citations in draft"

    # Check bibliography entries in References
    ref_entries = [line.strip() for line in refs_text.splitlines() if line.strip().startswith("- ")]
    assert len(ref_entries) >= 2, "Must contain at least 2 bibliography entries"

    # Verified sources
    sources = json.loads(verified_sources_file.read_text(encoding="utf-8"))
    assert len(sources) >= 2
    sources_by_id = {s["id"]: s for s in sources}
    sources_by_doi = {s.get("doi"): s for s in sources if s.get("doi")}

    # Verify each bibliography entry matches APA 7 and points to a verified DOI
    for ref in ref_entries:
        assert re.match(r"^-\s+[A-Z].+\(\d{4}\)\..+https://doi\.org/", ref), f"Invalid APA 7 reference format: {ref}"
        doi_match = re.search(r"https?://doi\.org/([^\s]+)", ref)
        assert doi_match is not None, f"Bibliography entry missing DOI: {ref}"
        doi = doi_match.group(1)
        assert doi in sources_by_doi, f"Fabricated or unverified DOI in reference: {doi}"

    # 2. Verify citation_map.json maintains bidirectional links
    cit_map = json.loads(citation_map_file.read_text(encoding="utf-8"))
    assert "citations" in cit_map
    citations = cit_map["citations"]
    assert len(citations) >= 4

    claims = json.loads(claims_file.read_text(encoding="utf-8"))
    claims_by_id = {c["id"]: c for c in claims}
    evidence_lines = [json.loads(line) for line in evidence_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence_by_id = {e["id"]: e for e in evidence_lines}

    for entry in citations:
        assert "citation_label" in entry
        assert "source_id" in entry
        assert "claim_id" in entry
        s_id = entry["source_id"]
        c_id = entry["claim_id"]
        e_id = entry.get("evidence_id")

        # Bidirectional link: source_id -> verified_sources
        assert s_id in sources_by_id, f"source_id {s_id} not in verified_sources"
        # Bidirectional link: claim_id -> claims
        assert c_id in claims_by_id, f"claim_id {c_id} not in claims"
        clm = claims_by_id[c_id]
        assert s_id in clm.get("supporting_sources", []), f"source {s_id} not in claim {c_id} supporting_sources"

        if e_id:
            assert e_id in evidence_by_id, f"evidence_id {e_id} not in evidence"
            assert e_id in clm.get("supporting_evidence", []), f"evidence {e_id} not in claim {c_id} supporting_evidence"
            ev = evidence_by_id[e_id]
            assert ev.get("claim_id") == c_id
            assert ev.get("source_id") == s_id

    # 3. Audit citation_audit.json and token hygiene
    cit_audit = json.loads(citation_audit_file.read_text(encoding="utf-8"))
    assert cit_audit.get("passed") is True
    assert cit_audit.get("orphan_citations") == []
    assert cit_audit.get("internal_tokens") == []
    assert cit_audit.get("author_year_orphans") == []

    # Independent token hygiene verification on draft.md
    assert detect_internal_tokens(draft_text) == []
    source_objs = [Source(**s) for s in sources]
    known_keys = {citation_key_for(s) for s in source_objs}
    assert detect_orphan_citations(draft_text, known_keys) == []
    assert detect_orphan_author_year_citations(draft_text, source_objs) == []


def test_property_7_consequential_claim_fact_audit_gate_and_publication_halting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feature: policy-safe-live-verification, Property 7: Consequential Claim Fact Audit Gate and Publication Halting.

    For any research run containing consequential claims (importance HIGH or CRITICAL, or causal assertions),
    if one or more such claims lack a recorded semantic review, fact_audit.json SHALL record passed: false,
    high-severity items SHALL be logged to review_queue.json, final.docx generation SHALL be refused
    (docx_path is None), needs_human_review SHALL be True, and the process SHALL terminate with exit code 1.

    Validates: Requirements 4.5, 4.6
    """
    project = _make_project(tmp_path, "prop7_consequential_proj")

    s1 = Source(
        id="src_prop7_1",
        title="Climate Warming and Crop Yield Shocks",
        authors=["Sutanto, H."],
        year=2023,
        venue="Agricultural Science Review",
        doi="10.1016/j.asr.2023.01",
        state=SourceState.APPROVED,
        abstract="Peningkatan suhu rata-rata menyebabkan penurunan produktivitas tanaman pangan secara terukur.",
    )
    ev1 = Evidence(
        id="evd_prop7_1",
        claim_id="clm_consequential",
        source_id="src_prop7_1",
        evidence_text="Peningkatan suhu rata-rata menyebabkan penurunan produktivitas tanaman pangan secara terukur.",
        location=EvidenceLocation(page=1),
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        verbatim=True,
        quote_verified=True,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    # Consequential claim: importance HIGH and causal assertion keyword 'menyebabkan'
    claim = Claim(
        id="clm_consequential",
        claim_text="Peningkatan suhu global menyebabkan krisis pangan di wilayah rentan.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=["src_prop7_1"],
        supporting_evidence=["evd_prop7_1"],
    )

    fixture_source(s1)
    ev1.extraction_method = ExtractionMethod.VERBATIM_ABSTRACT
    ev1.location = EvidenceLocation(locator="abstract")
    # 1. Execute workflow with NO semantic review passed
    workflow = DeepResearchWorkflow()
    response = workflow.execute(
        DeepResearchRequest(
            project=project,
            user_request="Dampak perubahan iklim terhadap ketahanan pangan",
            claims=[claim],
            evidence=[ev1],
            sources=[s1],
            semantic_reviews=[],  # Explicitly missing semantic review record
            generate_docx=True,
        )
    )

    # Verify publication halting invariants
    assert response.success is False
    assert response.needs_human_review is True
    assert response.docx_path is None
    assert not (project.directory / "final.docx").exists()
    assert "human_review" in response.stages

    # Verify fact_audit.json records passed: false and flags unreviewed consequential claim
    fact_audit_path = project.artifact_path(ProjectArtifact.FACT_AUDIT)
    assert fact_audit_path.is_file(), f"fact_audit.json must exist at {fact_audit_path}"
    fact_data = json.loads(fact_audit_path.read_text(encoding="utf-8"))
    assert fact_data["passed"] is False
    assert fact_data["semantic_passed"] is False or fact_data["structural_passed"] is False
    assert "clm_consequential" in fact_data["unsupported_claims"]
    assert any("consequential claim has no semantic review record" in r for r in fact_data["rejection_reasons"])

    # Verify high-severity review items are appended to review_queue.json
    queue_path = project.artifact_path(ProjectArtifact.REVIEW_QUEUE)
    assert queue_path.is_file(), f"review_queue.json must exist at {queue_path}"
    queue_data = json.loads(queue_path.read_text(encoding="utf-8"))
    assert len(queue_data) >= 1
    assert any(
        item.get("severity") in {"HIGH", "CRITICAL"}
        and ("consequential claim" in item.get("reason", "") or "Fact audit failed" in item.get("reason", ""))
        for item in queue_data
    )

    # 2. Verify CLI command execution terminates with exit code 1
    input_payload = {
        "project": {
            "name": "cli_prop7_proj",
            "workspace": "tmp",
            "path": str(tmp_path / "cli_prop7_proj"),
            "title": "CLI Prop 7 Test",
        },
        "topic": "Dampak kenaikan suhu terhadap tanaman pangan",
        "sources": [s1.to_dict()],
        "claims": [claim.to_dict()],
        "evidence": [ev1.to_dict()],
        "semantic_reviews": [],
    }
    payload_file = tmp_path / "input_prop7.json"
    payload_file.write_text(json.dumps(input_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    from src.tools.verification_tool import VerificationEngine
    monkeypatch.setattr("src.runtime.cli.VerificationEngine", lambda: VerificationEngine(providers=[]))

    cli_exit_code = main(["research", "--input-json", str(payload_file)])
    assert cli_exit_code == 1, "CLI deep research command must exit with code 1 on fact audit failure"


def test_audit_fact_audit_gate_enforcement_and_publication_halting() -> None:
    """Audit fact audit gate enforcement, publication halting, and review queue logging on real CLI run.

    - Verify that consequential claims lacking semantic review records result in passed: false in fact_audit.json
    - Verify high-severity review items are appended to review_queue.json
    - Verify publication halting: final.docx generation is refused (docx_path=None),
      needs_human_review=True, and command exits with exit code 1
    Validates: Requirements 4.5, 4.6
    """
    from src.core.paths import get_paths

    proj_dir = get_paths().workspace_path("TUGAS 1") / "dampak_perubahan_iklim_terhada"
    if not proj_dir.is_dir():
        pytest.skip("Project directory TUGAS 1/dampak_perubahan_iklim_terhada not present")

    # 1. Audit fact_audit.json
    fact_file = proj_dir / "fact_audit.json"
    assert fact_file.is_file(), "fact_audit.json must exist in project directory"
    fact_data = json.loads(fact_file.read_text(encoding="utf-8"))

    assert fact_data["passed"] is False, "fact_audit.json passed must be False"
    assert fact_data["semantic_passed"] is False, "fact_audit.json semantic_passed must be False"
    assert "clm_1" in fact_data["unsupported_claims"], "clm_1 must be flagged in unsupported_claims"
    assert "clm_2" in fact_data["unsupported_claims"], "clm_2 must be flagged in unsupported_claims"
    assert len(fact_data["rejection_reasons"]) >= 1, "fact_audit.json must contain rejection reasons"

    # Verify claim assessments
    assessments_by_id = {a["claim_id"]: a for a in fact_data.get("assessments", [])}
    assert "clm_1" in assessments_by_id
    assert "clm_2" in assessments_by_id
    assert assessments_by_id["clm_1"]["semantic_status"] in {"FAILED", "NOT_RUN"}
    assert assessments_by_id["clm_2"]["semantic_status"] in {"FAILED", "NOT_RUN"}

    # 2. Audit review_queue.json
    queue_file = proj_dir / "review_queue.json"
    assert queue_file.is_file(), "review_queue.json must exist in project directory"
    queue_data = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(queue_data) >= 1, "review_queue.json must contain review items"

    high_sev_items = [item for item in queue_data if item.get("severity") in {"HIGH", "CRITICAL"}]
    assert len(high_sev_items) >= 1, "review_queue.json must contain HIGH or CRITICAL severity review items"
    for item in high_sev_items:
        assert item.get("status") == "PENDING"
        assert item.get("recommended_action") == "Review and resolve audit findings before final publication"
        assert "Fact audit failed" in item.get("reason", "") or "claim" in item.get("reason", "")

    # 3. Audit publication halting across runs snapshots
    runs_dir = proj_dir / "runs"
    assert runs_dir.is_dir(), "runs directory must exist"
    run_folders = [d for d in runs_dir.iterdir() if d.is_dir()]
    assert len(run_folders) >= 1, "At least one run snapshot must exist"

    # Inspect runs that executed the research command
    research_runs = []
    for rf in run_folders:
        summary_file = rf / "run_summary.json"
        if summary_file.is_file():
            data = json.loads(summary_file.read_text(encoding="utf-8"))
            if data.get("command") == "research":
                research_runs.append((rf, data))

    assert len(research_runs) >= 1, "At least one CLI research run must exist"

    # For every research run where fact audit failed:
    for rf, summary in research_runs:
        assert summary["success"] is False, f"Research run {rf.name} must record success=False"
        assert summary["docx_path"] is None, f"Research run {rf.name} must refuse final.docx (docx_path=None)"
        assert summary["docx_relpath"] is None, f"Research run {rf.name} must have docx_relpath=None"
        assert "fact_audit" in summary.get("stages", []), f"Research run {rf.name} must execute fact_audit stage"
        assert "docx_generation" not in summary.get("stages", []), f"Research run {rf.name} must halt before docx_generation"
        assert "Fact audit failed" in summary.get("error_message", ""), f"Research run {rf.name} error message must record Fact audit failure"

        # Verify fact_audit_snapshot.json within the run folder
        snap_file = rf / "fact_audit_snapshot.json"
        assert snap_file.is_file(), f"Snapshot fact_audit_snapshot.json must exist in {rf.name}"
        snap_data = json.loads(snap_file.read_text(encoding="utf-8"))
        assert snap_data["passed"] is False, f"Snapshot fact audit passed must be False in {rf.name}"
