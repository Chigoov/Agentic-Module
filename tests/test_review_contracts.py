"""Small, offline acceptance checks for the 2026-10-10 review; no exploit/live-provider claims."""
import argparse
import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pypdf import PdfWriter

from conftest import fixture_source
from src.core.config import SystemConfig, ToolSection, load_config
from src.core.paths import SystemPaths
from src.core.project_manager import ProjectManager
from src.runtime import cli, execution, monitor
from src.schemas.evidence import Evidence, EvidenceLocation, ExtractionMethod
from src.schemas.project import Project
from src.schemas.review import ReviewItem, ReviewQueue
from src.schemas.source import Source
from src.tools.crossref import CrossrefTool
from src.tools.openalex import OpenAlexTool
from src.tools.http_client import HttpClient, read_bounded
from src.tools.pdf_parser import PDFParserTool, find_passage_page_location
from src.tools.retrieval import RetrievedPayload, RetrievalRequest, RetrievalTool, _public_destination, _PublicRedirect
from src.tools.source_content import stored_metadata, resolve_location, recheck_quote, sign_verification_snapshot
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow


def project_at(root):
    root.mkdir(parents=True, exist_ok=True)
    return Project(name=root.name, workspace=root.parent.name, path=str(root))


@pytest.mark.parametrize("provider_type", [CrossrefTool, OpenAlexTool])
def test_disabled_provider_never_calls_transport(provider_type, monkeypatch):
    from src.core.config import get_config
    from src.tools.research_tool import ResearchRequest
    provider = provider_type()
    monkeypatch.setitem(get_config().tools, provider.name, ToolSection(enabled=False))
    client = Mock(side_effect=AssertionError("No transport call permitted"))
    monkeypatch.setattr(provider, "_client", client)
    assert not provider.execute(ResearchRequest(query="dummy")).success
    assert provider.lookup_by_doi("10.1234/dummy") is None
    VerificationEngine(providers=[provider]).verify(Source(title="Dummy", authors=["A"], doi="10.1234/dummy"))
    client.assert_not_called()


def test_pdf_location_round_trip_preserves_global_raw_offsets(tmp_path):
    first = "Synthetic title\nMethods\n" + "Long first page. " * 40
    second = "Results\nActual  result\nacross whitespace.\nDiscussion\nDiscussed.\nReferences\nRef."
    text = first + "\n\n" + second
    pages = [{"page": 1, "text": first, "char_start": 0, "char_end": len(first)},
             {"page": 2, "text": second, "char_start": len(first)+2, "char_end": len(text)}]
    quote = "Actual result across whitespace."
    loc = find_passage_page_location(quote, pages)
    assert loc.page == 2 and loc.char_start > len(first)
    assert " ".join(resolve_location(text, pages, loc)["text"].split()) == quote
    artifact = tmp_path / "synthetic.json"
    artifact.write_text(json.dumps({"full_text": text, "pages": pages}), encoding="utf-8")
    source = Source(title="Synthetic title", retrieval_path=str(artifact), metadata={"retrieval": {
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "origin": "synthetic fixture",
        "retrieved_at": datetime.now(timezone.utc).isoformat()}})
    evidence = Evidence(source_id=source.id, claim_id="clm_dummy", evidence_text=quote,
        location=loc, extraction_method=ExtractionMethod.VERBATIM_FULLTEXT)
    assert recheck_quote(source, evidence) and evidence.quote_verified


def test_resume_rebases_and_rejected_project_has_no_writes(tmp_path, monkeypatch):
    system = tmp_path / "system"; system.mkdir()
    paths = SystemPaths(workspace_root=tmp_path, system_root=system)
    project = project_at(tmp_path / "moved")
    stale = project.model_copy(update={"path": str(tmp_path / "old")})
    manifest = project.directory / "project.json"; manifest.write_text(stale.model_dump_json(), encoding="utf-8")
    assert ProjectManager(paths=paths).load_manifest(manifest).directory == project.directory
    monkeypatch.setattr(execution, "get_paths", lambda: paths)
    forbidden = Project(name="forbidden", workspace="tmp", path=str(system))
    before = list(system.iterdir())
    result = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=forbidden, generate_docx=False))
    assert not result.success and list(system.iterdir()) == before


def test_prune_retains_active_unknown_and_corrupt_runs(tmp_path, capsys):
    project = project_at(tmp_path / "project")
    runs = project.directory / "runs"; runs.mkdir()
    for i in range(5):
        run = runs / f"run_{i}"; run.mkdir()
        (run / "run_summary.json").write_text(json.dumps({"run_id": run.name,
            "started_at": str(i), "finished_at": "2026-10-10T00:00:00+00:00", "success": True}))
    for name in ("run_active", "personal_notes", "run_corrupt"):
        (runs / name).mkdir()
    (runs / "run_active" / ".active").write_text("dummy active run")
    (runs / "run_active" / "run_summary.json").write_text(json.dumps({"run_id": "run_active", "started_at": "0",
        "finished_at": "2026-10-10T00:00:00+00:00", "success": True}))
    (runs / "run_corrupt" / "run_summary.json").write_text("[]")
    args = argparse.Namespace(project=str(project.directory), input_json=None, run_id=None, prune=True, keep=2)
    assert cli._cmd_runs(args) == 0
    assert json.loads(capsys.readouterr().out)["deleted_run_ids"] == ["run_2", "run_1", "run_0"]
    assert {p.name for p in runs.iterdir()} == {"run_4", "run_3", "run_active", "personal_notes", "run_corrupt"}


def test_project_lock_blocks_other_process_and_allows_other_project(tmp_path):
    first = project_at(tmp_path / "first"); second = project_at(tmp_path / "second")
    with execution.project_write_lock(first.directory):
        with execution.project_write_lock(first.directory), execution.project_write_lock(second.directory):
            code = "from pathlib import Path; from src.runtime.execution import project_write_lock; import sys\ntry:\n with project_write_lock(Path(sys.argv[1])): sys.exit(2)\nexcept RuntimeError: sys.exit(0)"
            result = subprocess.run([sys.executable, "-c", code, str(first.directory)], capture_output=True, timeout=10)
            assert result.returncode == 0, result.stderr.decode()
    assert not (first.directory / ".aai-active.lock").exists()


def handler_for(path, *, host="localhost:8123", origin="", token="", body=b"{}"):
    handler = object.__new__(monitor.MonitorHandler)
    handler.path = path
    handler.headers = {"Host": host, "Origin": origin, "X-Autonomi-Token": token, "Content-Length": str(len(body))}
    handler.server = SimpleNamespace(server_port=8123)
    handler.rfile = io.BytesIO(body)
    replies = []
    handler._json = lambda status, payload: replies.append((status, payload))
    return handler, replies


def test_monitor_mutations_are_authenticated_and_get_does_not_execute(monkeypatch):
    monkeypatch.setenv("AUTONOMI_API_TOKEN", "dummy-token")
    plan = Mock(return_value={"success": True}); monkeypatch.setattr(monitor, "_plan", plan)
    for route in ("/api/plan", "/api/check"):
        handler, replies = handler_for(route); handler.do_GET()
        assert replies[0][0] == 405
        for token in ("", "invalid"):
            handler, replies = handler_for(route, token=token); handler.do_POST()
            assert replies[0][0] == 401
    plan.assert_not_called()
    handler, replies = handler_for("/api/plan", token="dummy-token", origin="http://localhost:8123")
    handler.do_POST(); assert replies[0][0] == 200 and plan.call_count == 1
    for origin in ("http://evillocalhost:8123", "http://localhost:9999", "https://localhost:8123"):
        handler, replies = handler_for("/api/plan", token="dummy-token", origin=origin)
        handler.do_POST(); assert replies[0][0] == 403
    for host in ("evillocalhost:8123", "example.test:8123"):
        handler, replies = handler_for("/api/plan", token="dummy-token", host=host)
        handler.do_POST(); assert replies[0][0] == 403
    for origin in ("http://localhost:8123", "http://127.0.0.1:8123", "http://[::1]:8123"):
        handler, _ = handler_for("/api/plan", origin=origin)
        assert handler._origin_allowed()


def test_unsigned_import_and_stale_snapshot_are_not_current_verification(tmp_path):
    source = fixture_source(Source(title="Dummy", authors=["Smith, J."]), root=tmp_path, cache_report=True)
    path = Path(source.metadata["verification_artifact"]["path"])
    original = json.loads(path.read_bytes())
    for edit in ("unsigned", "old"):
        payload = dict(original); payload.pop("signature")
        if edit == "old":
            payload["verified_at"] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
            payload = sign_verification_snapshot(payload)
        raw = json.dumps(payload).encode(); path.write_bytes(raw)
        source.metadata["verification_artifact"]["sha256"] = hashlib.sha256(raw).hexdigest()
        assert stored_metadata(source) is None
    result = VerificationEngine(providers=[]).verify(source)
    assert result.recommended_state == "NEEDS_HUMAN_REVIEW"
    assert "verification_artifact" not in source.metadata and path.exists()


def test_bounded_read_and_error_body_stop_at_the_limit():
    for size in (8, 9):
        stream = io.BytesIO(b"x" * size)
        if size == 8:
            assert read_bounded(stream, 8) == b"x" * 8
        else:
            with pytest.raises(Exception, match="byte limit"):
                read_bounded(stream, 8)
        assert stream.tell() <= 9
    import urllib.error
    body = io.BytesIO(b"x" * 2500)
    exc = urllib.error.HTTPError("https://dummy.test", 400, "dummy", {}, body)
    HttpClient(tool_name="dummy")._to_integration_error("https://dummy.test", exc)
    assert body.tell() == 2000


def test_pdf_limits_and_blank_pages_are_explicit(monkeypatch):
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO(); writer.write(buffer)
    result = PDFParserTool().parse(buffer.getvalue())
    assert result.success and result.parser_version == "6.20.0" and result.unreadable_pages == [1]
    assert result.pages[0].text_status == "OCR_REQUIRED_OR_BLANK"
    from src.tools import pdf_parser
    monkeypatch.setattr(pdf_parser, "MAX_PDF_PAGES", 0)
    assert not PDFParserTool()._parse_local(buffer.getvalue()).success


def test_destination_validation_uses_only_stub_dns(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 80))])
    for url in ("file:///dummy", "http://dummy.test", "http://user:pass@dummy.test"):
        with pytest.raises(ValueError): _public_destination(url)
    with pytest.raises(ValueError):
        _PublicRedirect().redirect_request(None, None, 302, "", {}, "http://dummy.test")
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    _public_destination("https://dummy.test")


def test_failed_review_resolution_preserves_queue_and_history(tmp_path):
    project = project_at(tmp_path / "project")
    path = project.directory / "review_queue.json"
    ReviewQueue([ReviewItem(item_type="claim", item_id="clm_dummy", severity="HIGH", reason="Review claim", recommended_action="Inspect")]).save(path, root=project.directory)
    original = path.read_bytes()
    args = argparse.Namespace(project=str(project.directory), resolve="clm_dummy", input_json=None, notes="dummy", decision="SUPPORTED")
    assert cli._cmd_review_queue(args) == 1 and path.read_bytes() == original
    (project.directory / "fact_audit.json").write_text(json.dumps({"assessments": [{"claim_id": "clm_dummy", "evidence_id": "evd_dummy",
        "source_id": "src_dummy", "evidence_text": "Dummy excerpt", "evidence_location": "abstract"}]}))
    history = project.directory / "semantic_reviews.json"; history.write_text("{}")
    with pytest.raises(ValueError): cli._cmd_review_queue(args)
    assert path.read_bytes() == original and history.read_text() == "{}"


def test_dotenv_is_resolved_without_mutating_process_environment(tmp_path, monkeypatch):
    paths = SystemPaths(workspace_root=tmp_path, system_root=tmp_path)
    monkeypatch.delenv("DUMMY_KEY", raising=False)
    (tmp_path / ".env").write_text("DUMMY_KEY=dotenv-sentinel\nDUMMY_EMAIL=dummy@example.test\n")
    overrides = {"tools": {"dummy": {"api_key_env": "DUMMY_KEY", "contact_email_env": "DUMMY_EMAIL"}}}
    assert load_config(paths, overrides=overrides).tool("dummy").api_key == "dotenv-sentinel"
    assert load_config(paths, overrides=overrides, use_env=False).tool("dummy").api_key is None
    monkeypatch.setenv("DUMMY_KEY", "process-sentinel")
    assert load_config(paths, overrides=overrides).tool("dummy").api_key == "process-sentinel"


def test_metadata_conflicts_and_publication_updates_hold_verification():
    candidate = Source(title="Dummy paper", doi="10.1234/dummy", authors=["Smith, J."], year=2024, venue="Dummy Journal")
    class Provider:
        name = "dummy"
        def lookup_by_doi(self, doi): return record
    engine = VerificationEngine(providers=[Provider()])
    record = candidate.model_copy(update={"authors": ["John Smith"]})
    assert engine.verify(candidate).recommended_state == "DOI_VERIFIED"
    for update in ({"authors": ["Other, A."]}, {"year": 2020}, {"venue": "Other Journal"}, {"metadata": {"is_retracted": True}}):
        record = candidate.model_copy(update=update)
        assert engine.verify(candidate).recommended_state in {"CONDITIONAL", "NEEDS_HUMAN_REVIEW"}
        assert "verification_artifact" not in candidate.metadata


def test_literal_workbook_text_preserves_template_formulas(tmp_path):
    from openpyxl import load_workbook
    from test_quantitative_review_workbook import assessed_records, _template
    from src.tools.quantitative_review_workbook import build_quantitative_review_workbook
    records, template = assessed_records(1, tmp_path, _template())
    records[0]["title"] = "=1+1"
    digest = hashlib.sha256(Path(template).read_bytes()).hexdigest()
    result = build_quantitative_review_workbook(records, tmp_path / "literal.xlsx", template_path=template)
    workbook = load_workbook(result.workbook_path)
    cells = [c for sheet in workbook for row in sheet for c in row if c.value == "=1+1"]
    assert cells and all(c.data_type == "s" for c in cells)
    assert hashlib.sha256(Path(template).read_bytes()).hexdigest() == digest


def test_metadata_snapshot_is_bound_to_candidate_and_current_policy(tmp_path, monkeypatch):
    from src.core.config import get_config
    source = fixture_source(Source(title="Dummy binding", authors=["Smith, J."], year=2024), root=tmp_path)
    assert stored_metadata(source)
    for field, value in (("authors", ["Other, A."]), ("year", 2020), ("venue", "Other Journal")):
        changed = source.model_copy(update={field: value})
        assert stored_metadata(changed) is None
    config = get_config()
    changed = config.model_copy(update={"verification": config.verification.model_copy(update={"min_metadata_providers": 5})})
    monkeypatch.setattr("src.core.config.get_config", lambda: changed)
    assert stored_metadata(source) is None
    path = Path(source.metadata["verification_artifact"]["path"])
    snapshot = json.loads(path.read_bytes()); snapshot.pop("signature")
    snapshot["provider_records"][0]["provider"] = "crossref"
    raw = json.dumps(sign_verification_snapshot(snapshot)).encode()
    path.write_bytes(raw); source.metadata["verification_artifact"]["sha256"] = hashlib.sha256(raw).hexdigest()
    for status, expected in (("CONFIGURED", True), ("DISABLED", False), ("FAILED", False), ("PENDING_CONFIGURATION", False)):
        tools = {**config.tools, "crossref": ToolSection(enabled=True, status=status)}
        current = config.model_copy(update={"tools": tools})
        monkeypatch.setattr("src.core.config.get_config", lambda: current)
        assert bool(stored_metadata(source)) is expected


def test_configured_endpoints_and_verification_retries_use_shared_contract(monkeypatch):
    from src.tools.research_tool import ResearchRequest
    from src.tools.pubmed import PubMedTool
    from src.tools.semantic_scholar import SemanticScholarTool
    from src.tools.doab import DOABTool
    from src.tools.open_library import OpenLibraryTool
    from src.tools.http_client import HttpResult
    from src.workflows.deep_research import DeepResearchRequest
    config = SystemConfig(tools={name: ToolSection(enabled=True, status="CONFIGURED", base_url="https://dummy.test/sentinel")
        for name in ("crossref", "openalex", "semantic_scholar", "pubmed", "doab", "open_library")},
        research={"max_discovery_retries": 1, "max_verification_retries": 0})
    monkeypatch.setattr("src.core.config.get_config", lambda: config)
    for module in ("crossref", "openalex", "semantic_scholar", "pubmed", "doab", "open_library"):
        monkeypatch.setattr(f"src.tools.{module}.get_config", lambda: config)
    calls = []
    def fake_get(client, url, **kwargs):
        calls.append((url, client.max_retries))
        return HttpResult(url=url, status=200, headers={}, text="{}")
    monkeypatch.setattr(HttpClient, "get_json", fake_get)
    for tool, suffix in ((CrossrefTool(), "/works"), (OpenAlexTool(), "/works"), (SemanticScholarTool(), "/graph/v1/paper/search"),
                         (PubMedTool(), "/esearch.fcgi"), (DOABTool(), ""), (OpenLibraryTool(), "")):
        tool.execute(ResearchRequest(query="dummy"))
        assert calls[-1] == ("https://dummy.test/sentinel" + suffix, 1)
    CrossrefTool().lookup_by_doi("10.1234/dummy")
    assert calls[-1][0].startswith("https://dummy.test/sentinel/works/") and calls[-1][1] == 0
    OpenAlexTool().lookup_by_doi("10.1234/dummy")
    assert calls[-1][0].startswith("https://dummy.test/sentinel/works/doi:") and calls[-1][1] == 0
    with pytest.raises(ValueError):
        DeepResearchRequest(project=Project(name="dummy", workspace="dummy", path="dummy"), user_request="dummy", max_retries=1)


def test_failed_direct_download_is_attempted_once_before_landing_fallback(tmp_path):
    from src.agents.research import RetrievalAgent, RetrievalAgentRequest
    from src.schemas.source import AccessMode, RightsStatus, SourceType
    source = Source(title="Dummy book", source_type=SourceType.BOOK, url="https://dummy.test/landing",
        download_urls=["https://dummy.test/book.pdf"], access_mode=AccessMode.OPEN_DOWNLOAD, rights_status=RightsStatus.OPEN_LICENSE)
    calls = []
    def fetch(url, timeout):
        calls.append(url)
        if url.endswith(".pdf"):
            raise OSError("Dummy download failure")
        return RetrievedPayload(content=b"<h1>Dummy book</h1><p>Landing metadata only</p>", content_type="text/html", final_url=url)
    RetrievalAgent().execute(RetrievalAgentRequest(project=project_at(tmp_path / "project"), sources=[source], tool=RetrievalTool(fetcher=fetch)))
    assert calls == ["https://dummy.test/book.pdf", "https://dummy.test/landing"]
    assert not source.metadata["content_verification"]["full_text"]


def test_pdf_byte_text_timeout_and_parse_failure_are_bounded(tmp_path, monkeypatch):
    from src.tools import pdf_parser
    from test_book_download import _pdf_bytes
    content = _pdf_bytes("Dummy readable content")
    monkeypatch.setattr(pdf_parser, "MAX_PDF_TEXT", 1)
    assert "text limit" in PDFParserTool()._parse_local(content).error_message
    monkeypatch.setattr(pdf_parser, "MAX_PDF_BYTES", 1)
    assert not PDFParserTool().parse(content).success
    monkeypatch.setattr(pdf_parser, "MAX_PDF_BYTES", 50 * 1024 * 1024)
    process = Mock()
    process.poll.return_value = None
    process.communicate.side_effect = subprocess.TimeoutExpired("dummy", 0.01)
    launcher = Mock(return_value=process)
    monkeypatch.setattr(pdf_parser.subprocess, "Popen", launcher)
    monkeypatch.setattr(pdf_parser, "_limit_windows_worker", lambda process: None)
    monkeypatch.setenv("DUMMY_SECRET_NOT_FOR_WORKER", "dummy")
    assert not PDFParserTool().parse(content).success
    process.kill.assert_called_once(); process.wait.assert_called_once()
    assert "DUMMY_SECRET_NOT_FOR_WORKER" not in launcher.call_args.kwargs["env"]


def test_parent_section_contains_descendant_excerpt():
    text = "# Dummy\n## Methods\n### Participants\nDummy participants excerpt.\n## Results\nDummy results."
    location = resolve_location(text, [], {"section": "Methods"})
    assert "Dummy participants excerpt." in location["text"]
    assert "Dummy results." not in location["text"]


def test_skill_zip_matches_single_source_and_all_relative_references():
    import zipfile
    root = Path(__file__).resolve().parents[1]
    folder = root / "skills" / "autonomi-agentic-ilmiah"
    with zipfile.ZipFile(root / "dist" / "autonomi-agentic-ilmiah-skill.zip") as archive:
        expected = {"autonomi-agentic-ilmiah/" + p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        assert set(archive.namelist()) == set(expected)
        assert all(archive.read(name) == content for name, content in expected.items())
    from src.workflows.academic import AcademicWritingRequest
    payload = json.loads((folder / "references" / "input-synthetic.json").read_text(encoding="utf-8"))
    AcademicWritingRequest.model_validate(payload)


def test_same_initial_different_full_author_is_not_a_match():
    candidate = Source(title="Dummy author identity", authors=["Alice Smith"], doi="10.1234/dummy")
    class Provider:
        name = "dummy"
        def lookup_by_doi(self, doi): return candidate.model_copy(update={"authors": ["Aaron Smith"]})
    assert VerificationEngine(providers=[Provider()]).verify(candidate).recommended_state == "CONDITIONAL"


def test_provider_volume_issue_and_pages_reach_the_reference_formatter():
    from src.tools.reference_formatter import format_reference
    source = CrossrefTool()._item_to_source({"title": ["Dummy article"], "author": [{"family": "Smith", "given": "John"}],
        "issued": {"date-parts": [[2024]]}, "container-title": ["Dummy Journal"], "type": "journal-article",
        "volume": "12", "issue": "3", "page": "10-20"})
    assert (source.volume, source.issue, source.pages) == ("12", "3", "10-20")
    assert "12(3), 10-20" in format_reference(source).formatted


def test_mixed_text_and_blank_pdf_has_per_page_reading_status():
    from pypdf import PdfReader
    from test_book_download import _pdf_bytes
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(_pdf_bytes("Dummy text page"))).pages[0])
    writer.add_blank_page(width=300, height=300)
    stream = io.BytesIO(); writer.write(stream)
    result = PDFParserTool().parse(stream.getvalue())
    assert result.success and result.has_text_layer and result.ocr_required
    assert result.unreadable_pages == [2] and result.pages[1].text_status == "OCR_REQUIRED_OR_BLANK"


def test_preflight_probe_preserves_existing_file(tmp_path):
    project = project_at(tmp_path / "project")
    original = project.directory / ".aai_write_probe"
    original.write_bytes(b"Dummy preserved user file")
    execution.ensure_workflow_ready(project=project)
    assert original.read_bytes() == b"Dummy preserved user file"
    assert list(project.directory.iterdir()) == [original]


def test_finalize_and_export_reject_other_writer_before_reading(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.workflows.export_bundle import export_bundle
    project = project_at(tmp_path / "project")
    with execution.project_write_lock(project.directory), ThreadPoolExecutor(max_workers=1) as pool:
        args = argparse.Namespace(project=str(project.directory), project_flag=None, input_json=None, no_docx=True)
        for operation in (lambda: cli._cmd_finalize(args), lambda: export_bundle(project.directory)):
            with pytest.raises(execution.WorkflowReadinessError, match="active writer"):
                pool.submit(operation).result(timeout=5)
        assert {p.name for p in project.directory.iterdir()} == {".aai-active.lock"}
