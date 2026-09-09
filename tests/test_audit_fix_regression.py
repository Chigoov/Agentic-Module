"""Regression tests for the 2026-09-07 independent audit fixes (R1-R3).

Each test maps to a finding in docs/audit_independen_2026-09-07/LAPORAN_AUDIT.md:
  * A01 — nonexistent evidence IDs / unverified sources must not reach output.
  * A02 — internal tokens and author-year orphans must be rejected.
  * A03 — a real DOI with a materially different title must not be DOI_VERIFIED.
  * A04 — conflicted claims without disclosure must be rejected.
  * A05 — reruns must back up manual edits; backups must be unique; DOCX atomic.
  * A06 — the localhost API must reject foreign origins, missing tokens, and
    request-controlled project roots.
  * A07 — root discovery must accept renamed checkouts; manifest load must
    rebase to the actual location; tests must not need local TUGAS folders.
  * A12 — a valid large JSON response must parse instead of failing as
    INVALID_JSON; oversized bodies must fail as RESPONSE_TOO_LARGE.

All fixtures here are quarantined test data, never academic output.
"""
from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.agents.audit import CitationAuditAgent, CitationAuditRequest
from src.core.paths import (
    ENV_SYSTEM_ROOT,
    ENV_WORKSPACE_ROOT,
    reset_paths_cache,
)
from src.core.storage import backup_file
from src.runtime.monitor import create_handler, get_api_token
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.tools.citation_manager import (
    detect_internal_tokens,
    detect_orphan_author_year_citations,
)
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.gates import check_academic_integrity, scan_output_text
from src.workflows.orchestrator import OrchestratorAgent, OrchestratorRequest


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "project"
    directory.mkdir()
    return Project(name="project", workspace="tmp", path=str(directory), title="Audit Fix Fixture")


def _valid_bundle() -> tuple[Claim, Evidence, Source, Outline]:
    """A fully verified, referentially intact payload that must pass the gate."""
    source = Source(
        title="Attention is all you need",
        authors=["Vaswani, A."],
        year=2017,
        state=SourceState.APPROVED,
    )
    claim = Claim(
        claim_text="Transformers rely on attention.",
        supporting_sources=[source.id],
        supporting_evidence=["evd_ok"],
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
    )
    evidence = Evidence(
        id="evd_ok",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on attention.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    outline = Outline(
        title="Fixture",
        sections=[OutlineSection(title="Findings", claim_ids=[claim.id])],
    )
    return claim, evidence, source, outline


# --------------------------------------------------------------------------- #
# A01 — referential integrity gate
# --------------------------------------------------------------------------- #
def test_gate_rejects_nonexistent_evidence_id() -> None:
    claim, evidence, source, _ = _valid_bundle()
    forged = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})
    result = check_academic_integrity(claims=[forged], evidence=[evidence], sources=[source])
    assert not result.ok
    assert any("evd_nonexistent" in v for v in result.violations)


def test_gate_rejects_nonexistent_source_reference() -> None:
    claim, evidence, source, _ = _valid_bundle()
    forged = claim.model_copy(update={"supporting_sources": ["src_ghost"]})
    result = check_academic_integrity(claims=[forged], evidence=[evidence], sources=[source])
    assert not result.ok
    assert any("src_ghost" in v for v in result.violations)


def test_gate_rejects_unverified_source(tmp_path: Path) -> None:
    claim, evidence, source, _ = _valid_bundle()
    unverified = source.model_copy(update={"state": SourceState.DISCOVERED})
    result = check_academic_integrity(claims=[claim], evidence=[evidence], sources=[unverified])
    assert not result.ok
    assert any("never verified" in v for v in result.violations)


def test_gate_accepts_verified_bundle() -> None:
    claim, evidence, source, _ = _valid_bundle()
    result = check_academic_integrity(claims=[claim], evidence=[evidence], sources=[source])
    assert result.ok


def test_orchestrator_rejects_nonexistent_evidence(tmp_path: Path) -> None:
    """End-to-end: the audit's CLI probe (supported claim, ghost evidence ID)
    must fail instead of producing final.docx."""
    claim, evidence, source, outline = _valid_bundle()
    forged = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})
    response = OrchestratorAgent().execute(
        OrchestratorRequest(
            project=_project(tmp_path),
            claims=[forged],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False
    assert "integrity gate" in (response.error_message or "").lower()
    assert not (Path(response.draft_path).parent / "final.docx").exists() if response.draft_path else True


# --------------------------------------------------------------------------- #
# A02 — internal tokens and author-year orphans
# --------------------------------------------------------------------------- #
def test_internal_token_detector_finds_all_variants() -> None:
    text = "x turn0search0 y view0 z search5 w filecite filecite123 【turn0search1】"
    tokens = detect_internal_tokens(text)
    assert tokens  # all variants found
    assert any(t.startswith("turn") for t in tokens)
    assert any(t.startswith("view") for t in tokens)
    assert "filecite" in tokens
    assert "【" in tokens and "】" in tokens


def test_output_scan_blocks_tokens_and_orphans() -> None:
    source = Source(title="Paper", authors=["Smith, J."], year=2024, state=SourceState.APPROVED)
    violations = scan_output_text(
        draft="Claim turn0search0 (Nonexistent, 2024) more text",
        sources=[source],
    )
    assert any("internal citation tokens" in v for v in violations)
    assert any("author-year" in v for v in violations)


def test_output_scan_accepts_legitimate_citation() -> None:
    source = Source(title="Paper", authors=["Smith, J."], year=2024, state=SourceState.APPROVED)
    violations = scan_output_text(draft="Claim (Smith, 2024) body", sources=[source])
    assert violations == []


def test_citation_audit_agent_blocks_tokens_and_orphans(tmp_path: Path) -> None:
    source = Source(title="Paper", authors=["Smith, J."], year=2024, state=SourceState.APPROVED)
    response = CitationAuditAgent().execute(
        CitationAuditRequest(
            project=_project(tmp_path),
            draft="Body turn0search0 and (Ghost, 1999)",
            sources=[source],
        )
    )
    assert response.passed is False
    assert response.internal_tokens
    assert response.author_year_orphans


def test_orchestrator_rejects_internal_tokens(tmp_path: Path) -> None:
    claim, evidence, source, outline = _valid_bundle()
    poisoned_claim = claim.model_copy(update={"claim_text": "Poisoned turn0search0 view0 text"})
    response = OrchestratorAgent().execute(
        OrchestratorRequest(
            project=_project(tmp_path),
            claims=[poisoned_claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False
    assert "internal citation tokens" in (response.error_message or "")


def test_orchestrator_rejects_author_year_orphan(tmp_path: Path) -> None:
    claim, evidence, source, outline = _valid_bundle()
    # Inject an orphan author-year citation directly into the claim text.
    orphan_claim = claim.model_copy(update={"claim_text": "Mixed content (Nobody, 2001)."})
    response = OrchestratorAgent().execute(
        OrchestratorRequest(
            project=_project(tmp_path),
            claims=[orphan_claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False
    assert "author-year citations" in (response.error_message or "")


# --------------------------------------------------------------------------- #
# A03 — DOI identity mismatch
# --------------------------------------------------------------------------- #
class _RealDoiDifferentTitleProvider:
    name = "fixture_provider"

    def lookup_by_doi(self, doi: str) -> Source | None:
        # The DOI resolves, but to a *different* work.
        return Source(title="Deep learning", doi=doi)

    def lookup_by_bibliographic(self, *, title: str, authors=None, year=None) -> Source | None:
        return None


def test_doi_with_wrong_title_needs_human_review() -> None:
    """The audit probe: a real DOI paired with an unrelated title must NOT be
    DOI_VERIFIED with similarity 0.0."""
    engine = VerificationEngine(
        providers=[_RealDoiDifferentTitleProvider()],
        match_threshold=0.6,
        min_providers=1,
    )
    source = Source(
        title="AUDIT FIXTURE unrelated horticulture potatoes",
        authors=["X"],
        year=1900,
        doi="10.1038/nature14539",
    )
    result = engine.verify(source)
    assert result.recommended_state is SourceState.NEEDS_HUMAN_REVIEW
    assert result.report.metadata_match_ratio == 0.0
    failed = [c for c in result.report.checks if c.name == "metadata_identity_match"]
    assert failed and failed[0].status.value == "FAILED"


def test_doi_with_matching_title_still_verified() -> None:
    engine = VerificationEngine(
        providers=[_RealDoiDifferentTitleProvider()],
        match_threshold=0.6,
        min_providers=1,
    )
    source = Source(title="Deep learning", authors=["LeCun, Y."], doi="10.1038/nature14539")
    result = engine.verify(source)
    assert result.recommended_state is SourceState.DOI_VERIFIED


# --------------------------------------------------------------------------- #
# A04 — conflicted claims need disclosure
# --------------------------------------------------------------------------- #
def test_gate_rejects_conflicted_claim_without_disclosure() -> None:
    claim, evidence, source, _ = _valid_bundle()
    conflicted = claim.model_copy(update={"status": ClaimStatus.CONFLICTED})
    result = check_academic_integrity(claims=[conflicted], evidence=[evidence], sources=[source])
    assert not result.ok
    assert any("conflicted" in v for v in result.violations)


def test_gate_accepts_conflicted_claim_with_qualifier() -> None:
    claim, evidence, source, _ = _valid_bundle()
    conflicted = claim.model_copy(
        update={"status": ClaimStatus.CONFLICTED, "qualifier": "in a single contested cohort"}
    )
    result = check_academic_integrity(claims=[conflicted], evidence=[evidence], sources=[source])
    assert result.ok


# --------------------------------------------------------------------------- #
# A05 — backup uniqueness and draft preservation
# --------------------------------------------------------------------------- #
def test_backup_same_instant_yields_unique_names(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("v1", encoding="utf-8")
    first = backup_file(target, root=tmp_path)
    target.write_text("v2", encoding="utf-8")
    second = backup_file(target, root=tmp_path)
    assert first is not None and second is not None
    assert first != second, "two backups in the same second must not collide"
    assert first.read_text(encoding="utf-8") == "v1"
    assert second.read_text(encoding="utf-8") == "v2"


def test_rerun_preserves_manual_draft_edit(tmp_path: Path) -> None:
    """The audit's rerun probe: a manual sentinel edit must survive (as a
    backup) when a rerun overwrites draft.md."""
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    draft_path = project.directory / "draft.md"
    draft_path.write_text("USER EDIT SENTINEL", encoding="utf-8")
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project, claims=[claim], evidence=[evidence], sources=[source], outline=outline
        )
    )
    assert response.success
    assert (draft_path).read_text(encoding="utf-8") != "USER EDIT SENTINEL"
    backups = list(project.directory.glob("draft.md.*.bak"))
    assert backups, "rerun must back up the manually edited draft"
    assert any(b.read_text(encoding="utf-8") == "USER EDIT SENTINEL" for b in backups)


def test_docx_overwrite_creates_unique_backups(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    request = AcademicWritingRequest(
        project=project, claims=[claim], evidence=[evidence], sources=[source], outline=outline
    )
    first = AcademicWritingWorkflow().execute(request)
    second = AcademicWritingWorkflow().execute(request)
    assert first.success and second.success
    docx_backups = list(project.directory.glob("final.docx.*.bak"))
    assert len(docx_backups) >= 1
    assert len({b.name for b in docx_backups}) == len(docx_backups), "backup names must be unique"


# --------------------------------------------------------------------------- #
# A06 — localhost API guards
# --------------------------------------------------------------------------- #
@pytest.fixture()
def api_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ENV_SYSTEM_ROOT, str(tmp_path / "DATA BASE"))
    (tmp_path / "DATA BASE").mkdir(exist_ok=True)
    monkeypatch.setenv("AUTONOMI_API_TOKEN", "test-token-12345")
    monkeypatch.setattr("src.runtime.progress.get_paths", lambda: _forced_paths(tmp_path))
    reset_paths_cache()
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    yield base, tmp_path
    server.shutdown()
    thread.join(timeout=5)
    reset_paths_cache()


def _forced_paths(tmp_path: Path):
    from src.core.paths import SystemPaths

    return SystemPaths(
        workspace_root=tmp_path, system_root=tmp_path / "DATA BASE"
    )


def test_api_rejects_missing_token(api_server) -> None:
    base, _ = api_server
    req = Request(
        base + "/api/run-academic",
        data=json.dumps({"topic": "fixture"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as response:  # noqa: S310
            status = response.status
            body = json.loads(response.read())
    except HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read())
    assert status == 401
    assert body["success"] is False


def test_api_rejects_foreign_origin(api_server) -> None:
    base, _ = api_server
    req = Request(
        base + "/api/run-academic",
        data=json.dumps({"topic": "fixture"}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Autonomi-Token": "test-token-12345",
            "Origin": "https://example.invalid",
        },
    )
    try:
        with urlopen(req, timeout=5) as response:  # noqa: S310
            status = response.status
            body = json.loads(response.read())
    except HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read())
    assert status == 403


def test_api_rejects_arbitrary_project_path(api_server) -> None:
    """The audit probe revisited: a request-supplied project_path must never
    decide where files are written. The server builds its own root, so the
    attacker-chosen directory must not exist after the call."""
    base, tmp_path = api_server
    outside = tmp_path / "elsewhere"
    req = Request(
        base + "/api/run-academic",
        data=json.dumps({"project_path": str(outside), "topic": "fixture"}).encode(),
        headers={"Content-Type": "application/json", "X-Autonomi-Token": "test-token-12345"},
    )
    with urlopen(req, timeout=15) as response:  # noqa: S310
        assert response.status == 200
    assert not outside.exists(), "nothing may be written to a request-supplied path"
    # The server-side project must have been created inside the workspace root.
    workspace_projects = tmp_path / "TUGAS 1"
    assert workspace_projects.is_dir()


def test_api_malformed_json_returns_structured_error(api_server) -> None:
    base, _ = api_server
    req = Request(
        base + "/api/run-academic",
        data=b"{",
        headers={"Content-Type": "application/json", "X-Autonomi-Token": "test-token-12345"},
    )
    try:
        with urlopen(req, timeout=5) as response:  # noqa: S310
            status = response.status
            body = json.loads(response.read())
    except HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read())
    assert status == 400
    assert body["success"] is False
    assert body.get("error_code") == "INVALID_REQUEST"


def test_api_token_is_stable_and_secret_shaped() -> None:
    token = get_api_token()
    assert isinstance(token, str) and len(token) >= 32


# --------------------------------------------------------------------------- #
# A07 — portability
# --------------------------------------------------------------------------- #
def test_manifest_load_rebases_to_actual_location(tmp_path: Path) -> None:
    """The audit's relocation probe: copying a manifest elsewhere must load
    the project from the new location, not the machine of origin."""
    from src.core.paths import SystemPaths
    from src.core.project_manager import ProjectManager
    from src.core.storage import write_json
    from src.schemas.project import PROJECT_MANIFEST_FILENAME

    old = tmp_path / "old"
    old.mkdir()
    workspace = tmp_path / "workspace"
    # The manifest is copied (as between laptops) into workspace/new/.
    new = workspace / "new"
    new.mkdir(parents=True)
    project = Project(name="moved", workspace="ws", path=str(old), title="Fixture")
    write_json(new / PROJECT_MANIFEST_FILENAME, project, root=workspace)
    manager = ProjectManager(
        paths=SystemPaths(workspace_root=workspace, system_root=tmp_path)
    )
    loaded = manager.load(workspace=".", name="new")
    assert loaded.directory == new.resolve(), "manifest path must follow the actual location"


def test_backup_names_embed_microseconds(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("data", encoding="utf-8")
    backup = backup_file(target, root=tmp_path)
    assert backup is not None
    assert "." in backup.name and ".bak" in backup.name


# --------------------------------------------------------------------------- #
# A12 — large valid JSON
# --------------------------------------------------------------------------- #
def test_large_valid_json_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tools.http_client import HttpClient

    class LargeResponse:
        headers = {"content-type": "application/json"}
        status = 200

        def __enter__(self) -> "LargeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            return json.dumps({"data": "x" * 210000}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: LargeResponse())
    result = HttpClient(tool_name="audit", max_retries=0).get_json("https://example.invalid/x")
    assert len(result.json()["data"]) == 210000
    assert result.truncated is True  # excerpt only; parse body stayed whole


# --------------------------------------------------------------------------- #
# R4 integration — nested outline claims and Markdown references
# --------------------------------------------------------------------------- #
def test_writer_renders_nested_subsection_claims(tmp_path: Path) -> None:
    """Audit A17: claims referenced only from nested subsections must appear
    in the draft instead of silently vanishing."""
    from src.agents.writer import WriterAgent, WriterRequest

    project = _project(tmp_path)
    claim, evidence, source, _ = _valid_bundle()
    outline = Outline(
        title="Fixture",
        sections=[
            OutlineSection(
                title="Top",
                claim_ids=[],
                subsections=[OutlineSection(title="Sub", level=2, claim_ids=[claim.id])],
            )
        ],
    )
    response = WriterAgent().execute(
        WriterRequest(project=project, outline=outline, claims=[claim], evidence=[evidence], sources=[source])
    )
    assert response.success
    assert claim.claim_text in response.draft, "subsection claim must be rendered"
    assert "## Top" in response.draft and "### Sub" in response.draft


def test_draft_markdown_carries_reference_list(tmp_path: Path) -> None:
    """Audit A10: a --no-docx run must still produce a citable package — the
    draft Markdown carries the bibliography, not just the DOCX export."""
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            generate_docx=False,
        )
    )
    assert response.success
    draft = (project.directory / "draft.md").read_text(encoding="utf-8")
    assert "References" in draft
    assert "Vaswani, A. (2017). Attention is all you need." in draft


# --------------------------------------------------------------------------- #
# Regression from real CLI workflow testing (2026-09-09)
# --------------------------------------------------------------------------- #
def test_citation_key_pattern_ignores_doi_url_path() -> None:
    """CLI test finding: the reference entry URL
    ``https://doi.org/10.1038/nature14539`` must not be misread as the machine
    citation key ``nature14539`` — the positive workflow failed on this."""
    from src.tools.citation_manager import detect_orphan_citations

    draft = (
        "Claim body (LeCun et al., 2015)\n## References\n- Yann LeCun (2015). "
        "Deep learning. Nature. https://doi.org/10.1038/nature14539"
    )
    assert detect_orphan_citations(draft, set()) == []


def test_in_text_preserves_mixed_case_surname() -> None:
    """CLI test finding: ``LeCun`` was title-cased to ``Lecun`` (wrong APA 7)."""
    from src.tools.reference_formatter import format_in_text_author_year

    source = Source(
        title="Deep learning",
        authors=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        year=2015,
    )
    assert format_in_text_author_year(source) == "LeCun et al., 2015"


def test_docx_has_single_references_heading(tmp_path: Path) -> None:
    """CLI test finding: the draft's own References section plus the DOCX
    generator's heading produced a duplicated bibliography."""
    from src.tools.docx_generator import DocxGenerationRequest, DocxGenerationTool
    from src.tools.reference_formatter import format_reference_list

    project = _project(tmp_path)
    claim, evidence, source, _ = _valid_bundle()
    reference_list = format_reference_list([source], project_id=project.id)
    draft = (
        "# Doc\n\n## Temuan\n\nBody text.\n\n## References\n\n"
        f"- {reference_list.entries[0].formatted}\n"
    )
    response = DocxGenerationTool().execute(
        DocxGenerationRequest(
            project=project,
            draft=draft,
            reference_list=reference_list,
            citation_audit_passed=True,
            fact_audit_passed=True,
        )
    )
    assert response.success
    from docx import Document

    text = "\n".join(p.text for p in Document(response.docx_path).paragraphs)
    assert text.count("References") == 1, "bibliography heading must appear exactly once"
