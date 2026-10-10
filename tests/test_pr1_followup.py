"""Dummy/offline regressions for PR #1 follow-up; no live research qualification."""
import argparse
import io
import json
import hashlib
import hmac
import os
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.runtime import cli
from src.schemas.claim import SemanticReview
from src.schemas.project import Project
from src.schemas.review import ReviewItem, ReviewQueue
from src.schemas.source import Source
from src.schemas.source import AccessMode, RightsStatus, SourceType, SourceState
from src.schemas.evidence import ReadingDepth
from src.core.storage import read_jsonl
from src.agents.research import RetrievalAgent, RetrievalAgentRequest, RetrievalAgentResponse
from src.tools.retrieval import RetrievalTool, RetrievalRequest, RetrievalResponse, RetrievedPayload
from src.tools.pdf_parser import PDFParserTool
from src.tools.research_tool import ResearchTool
from src.workflows.deep_research import DeepResearchWorkflow, DeepResearchRequest
from conftest import fixture_source
from pypdf import PdfWriter
from src.core.config import get_config
from src.tools.source_content import sign_verification_snapshot, stored_metadata
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingResponse, AcademicWritingWorkflow


def project_at(root):
    root.mkdir(parents=True, exist_ok=True)
    return Project(name=root.name, workspace=root.parent.name, path=str(root))


@pytest.mark.parametrize("history", [b"{}", b'""', b'[{}]'])
def test_history_rejected_before_workflow_writes(tmp_path, monkeypatch, history):
    from src.workflows import academic
    project = project_at(tmp_path / "project")
    sem = project.directory / "semantic_reviews.json"
    queue = project.directory / "review_queue.json"
    sem.write_bytes(history)
    queue.write_bytes(b"[]\n")
    monkeypatch.setattr(academic, "ensure_workflow_ready", lambda **kw: {})
    writes = Mock(side_effect=AssertionError("invalid history reached a project write"))
    monkeypatch.setattr(academic, "write_json", writes)
    with pytest.raises(ValueError):
        AcademicWritingWorkflow()._run(AcademicWritingRequest(project=project, generate_docx=False))
    assert sem.read_bytes() == history and queue.read_bytes() == b"[]\n"
    writes.assert_not_called()


def test_valid_history_loader(tmp_path):
    path = tmp_path / "semantic_reviews.json"
    assert SemanticReview.load_history(path) == []
    review = SemanticReview(claim_id="clm_dummy", reason="synthetic review")
    path.write_text(json.dumps([review.model_dump(mode="json")]), encoding="utf-8")
    assert SemanticReview.load_history(path) == [review]


@pytest.mark.parametrize("operation", ["runs", "review_queue", "finalize"])
def test_operation_resolves_once_and_consumes_locked_project(tmp_path, monkeypatch, operation, capsys):
    a, b = project_at(tmp_path / "A"), project_at(tmp_path / "B")
    resolver = Mock(side_effect=[a.directory, b.directory])
    monkeypatch.setattr(cli, "_resolve_project_dir", resolver)
    item = ReviewItem(item_type="source", item_id="src_dummy", severity="LOW",
                      reason="synthetic review", recommended_action="inspect")
    for project in (a, b):
        ReviewQueue([item.model_copy(deep=True)]).save(project.directory / "review_queue.json", root=project.directory)
    observed = []
    def finalize(self, request):
        observed.append(request.project.directory)
        assert (a.directory / ".aai-active.lock").is_file()
        return AcademicWritingResponse(success=True)
    monkeypatch.setattr(AcademicWritingWorkflow, "execute", finalize)
    args = argparse.Namespace(prune=True, keep=1, resolve=item.id, notes="dummy", no_docx=True)
    assert getattr(cli, "_cmd_" + operation)(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert resolver.call_count == 1
    if operation == "finalize":
        assert observed == [a.directory]
    else:
        assert output["project_directory"] == str(a.directory)
    if operation == "review_queue":
        assert ReviewQueue.load(a.directory / "review_queue.json").items[0].status == "RESOLVED"
        assert ReviewQueue.load(b.directory / "review_queue.json").items[0].status == "PENDING"


def snapshot_data(source):
    from src.core.config import get_config
    return dict(source_id=source.id, title=source.title, doi=source.doi, authors=source.authors,
                year=source.year, venue=source.venue, verified_at=datetime.now(timezone.utc).isoformat(),
                verification_policy=get_config().verification.model_dump(mode="json"),
                provider_records=[dict(provider="synthetic provider", record=source.model_dump(mode="json"))])


def save_snapshot(source, data, root):
    raw = json.dumps(data).encode()
    path = root / (source.id + ".json")
    path.write_bytes(raw)
    source.metadata["verification_artifact"] = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def use_scratch_cache(monkeypatch, root):
    monkeypatch.setattr("src.core.paths.get_paths", lambda: SimpleNamespace(cache_dir=root))
    monkeypatch.setattr("src.tools.verification_tool.get_paths", lambda: SimpleNamespace(cache_dir=root))


def use_verification_policy(monkeypatch, **values):
    cfg = get_config().model_copy(update={"verification": get_config().verification.model_copy(update=values)})
    monkeypatch.setattr("src.core.config.get_config", lambda: cfg)
    monkeypatch.setattr("src.tools.verification_tool.get_config", lambda: cfg)
    return cfg


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr("socket.create_connection", Mock(side_effect=AssertionError("No network in dummy regressions")))


def test_key_not_published_while_random_bytes_are_prepared(tmp_path, monkeypatch):
    use_scratch_cache(monkeypatch, tmp_path)
    key = tmp_path / "verification" / ".snapshot-key"
    def prepare(size):
        assert not key.exists(), "reader can already see the unfinished key"
        return b"k" * size
    monkeypatch.setattr("src.tools.source_content.secrets.token_bytes", prepare)
    sign_verification_snapshot({"dummy": True})
    assert key.read_bytes() == b"k" * 32
    first = key.read_bytes()
    sign_verification_snapshot({"dummy": False})
    assert key.read_bytes() == first


@pytest.mark.parametrize("key_bytes", [b"", b"short", b"k" * 33])
def test_invalid_key_refused_for_signing_and_verification(tmp_path, monkeypatch, key_bytes):
    use_scratch_cache(monkeypatch, tmp_path)
    source = Source(title="Synthetic source", authors=["A"])
    save_snapshot(source, sign_verification_snapshot(snapshot_data(source)), tmp_path)
    key = tmp_path / "verification" / ".snapshot-key"
    key.write_bytes(key_bytes)
    data = snapshot_data(source)
    data["signature"] = hmac.digest(key_bytes, json.dumps(data, ensure_ascii=False, sort_keys=True).encode(), "sha256").hex()
    save_snapshot(source, data, tmp_path)
    assert stored_metadata(source) is None
    with pytest.raises(ValueError, match="32"):
        sign_verification_snapshot(snapshot_data(source))
    assert stored_metadata(source) is None
    assert key.read_bytes() == key_bytes


def test_two_process_first_use_snapshots_verify(tmp_path, monkeypatch):
    use_scratch_cache(monkeypatch, tmp_path)
    sources = [Source(title="Synthetic source", authors=["A"]) for _ in range(2)]
    # Two interpreters start signing together in an empty, private scratch cache.
    script = """
import json,sys,time
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=[sys.argv[3],sys.argv[4]]
import src.core.paths
from src.tools.source_content import sign_verification_snapshot
root=Path(sys.argv[1]); source_id=sys.argv[2]
src.core.paths.get_paths=lambda: SimpleNamespace(cache_dir=root)
data=json.load(sys.stdin)
(root/(source_id+'.ready')).touch()
deadline=time.monotonic()+20
while len(list(root.glob('*.ready')))<2:
    if time.monotonic()>deadline: raise TimeoutError('start barrier')
    time.sleep(.01)
(root/(source_id+'.json')).write_text(json.dumps(sign_verification_snapshot(data)),encoding='utf-8')
"""
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH") if k in os.environ}
    processes = [subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-I", "-c", script,
                 str(tmp_path), s.id, str(Path.cwd()), sysconfig.get_paths()["purelib"]],
                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for s in sources]
    jobs = []
    try:
        if os.name == "nt":
            from src.tools.pdf_parser import _limit_windows_worker
            for process in processes:
                jobs.append(_limit_windows_worker(process))
        for process, source in zip(processes, sources):
            process.stdin.write(json.dumps(snapshot_data(source)).encode())
            process.stdin.close()
        for process in processes:
            assert process.wait(timeout=30) == 0, process.stderr.read().decode()
        for source in sources:
            raw = (tmp_path / (source.id + ".json")).read_bytes()
            source.metadata["verification_artifact"] = dict(path=str(tmp_path / (source.id + ".json")), sha256=hashlib.sha256(raw).hexdigest())
            assert stored_metadata(source) is not None
        assert len((tmp_path / "verification" / ".snapshot-key").read_bytes()) == 32
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
        if jobs:
            import ctypes
            kernel = ctypes.WinDLL("kernel32")
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            for job in jobs:
                kernel.CloseHandle(job)


@pytest.mark.parametrize("kind", ["minimum", "threshold", "reload", "reload_enabled"])
def test_snapshot_records_effective_policy_and_consumer_enforces_current(tmp_path, monkeypatch, kind):
    use_scratch_cache(monkeypatch, tmp_path)
    use_verification_policy(monkeypatch, min_metadata_providers=2 if kind == "minimum" else 1, metadata_match_threshold=.8)
    engine = VerificationEngine(providers=[SimpleNamespace(name="synthetic provider")],
                                min_providers=1, match_threshold=.6)
    if kind == "reload":
        use_verification_policy(monkeypatch, min_metadata_providers=1, metadata_match_threshold=.9)
    elif kind == "reload_enabled":
        use_verification_policy(monkeypatch, min_metadata_providers=1, metadata_match_threshold=.8, enabled=False)
    source = Source(title="Synthetic source", authors=["A"], year=2020)
    monkeypatch.setattr(engine, "_fetch_record", lambda *args: source.model_copy(deep=True))
    engine.verify(source)
    raw = json.loads(Path(source.metadata["verification_artifact"]["path"]).read_bytes())
    assert raw["verification_policy"] == dict(enabled=True, metadata_match_threshold=.6, min_metadata_providers=1)
    assert stored_metadata(source) is None


def test_duplicate_provider_records_do_not_meet_minimum(tmp_path, monkeypatch):
    use_scratch_cache(monkeypatch, tmp_path)
    use_verification_policy(monkeypatch, min_metadata_providers=2)
    source = Source(title="Synthetic source", authors=["A"])
    data = snapshot_data(source)
    data["provider_records"] *= 2
    save_snapshot(source, sign_verification_snapshot(data), tmp_path)
    assert stored_metadata(source) is None
    data["provider_records"][1] = dict(data["provider_records"][1], provider="second synthetic provider")
    save_snapshot(source, sign_verification_snapshot(data), tmp_path)
    assert stored_metadata(source) is not None


def test_consumer_uses_one_config_snapshot(tmp_path, monkeypatch):
    use_scratch_cache(monkeypatch, tmp_path)
    source = Source(title="Synthetic source", authors=["A"])
    save_snapshot(source, sign_verification_snapshot(snapshot_data(source)), tmp_path)
    config = Mock(return_value=get_config())
    monkeypatch.setattr("src.core.config.get_config", config)
    assert stored_metadata(source) is not None
    assert config.call_count == 1


@pytest.mark.parametrize("method,proof,accepted", [("url", False, False), ("url", None, False), ("url", True, True), ("abstract", False, True)])
def test_fallback_has_same_content_gate_as_primary(tmp_path, monkeypatch, method, proof, accepted):
    project = project_at(tmp_path / "project")
    source = Source(title="Synthetic source", access_mode=AccessMode.OPEN_DOWNLOAD, rights_status=RightsStatus.OPEN_LICENSE,
                    download_urls=["https://synthetic.invalid/file.pdf"])
    tool = RetrievalTool()
    calls = []
    def retrieve(request):
        calls.append(request)
        if len(calls) == 1:
            return RetrievalResponse(success=False, source=source)
        source.metadata["content_verification"] = {} if proof is None else {"full_text": proof}
        return RetrievalResponse(source=source, parsed_text="Synthetic retrieved text.", retrieval_method=method)
    monkeypatch.setattr(tool, "execute", retrieve)
    response = RetrievalAgent()._execute(RetrievalAgentRequest(project=project, sources=[source], tool=tool))
    assert bool(response.parsed_text_by_source) is accepted
    assert response.needs_human_review is (not accepted)
    assert response.failed == ([] if accepted else [source.id])
    assert len(calls) == 2 and not calls[1].allow_direct_download


@pytest.mark.parametrize("kind", ["partial", "heuristic_only", "quote_failure", "examined"])
def test_automatic_evidence_has_no_unproven_reading_assurance(tmp_path, monkeypatch, synthetic_verifier, kind):
    project = project_at(tmp_path / "project")
    source = Source(title="Synthetic source", authors=["A"], year=2020, state=SourceState.APPROVED,
                    abstract="A synthetic abstract describing a small dummy study.")
    fixture_source(source, root=project.directory / "source_documents")
    if kind == "partial":
        Path(source.retrieval_path).write_text(source.title + "\nLanding page sentence with no complete document content.")
        source.metadata["retrieval"]["sha256"] = hashlib.sha256(Path(source.retrieval_path).read_bytes()).hexdigest()
    text = "This synthetic retrieved body sentence is a candidate for review."
    if kind in {"heuristic_only", "examined"}:
        text = Path(source.retrieval_path).read_text()
    if kind == "examined":
        source.metadata["examination"] = dict(source_id=source.id, artifact_sha256=source.metadata["retrieval"]["sha256"],
            reviewer="synthetic reviewer", reviewed_at=datetime.now(timezone.utc).isoformat(), scope="full",
            sections=[dict(section="Methods", excerpt=source.abstract), dict(section="Results", excerpt="Fixture result."),
                      dict(section="Discussion", excerpt="Fixture discussion.")])
    monkeypatch.setattr(RetrievalAgent, "execute", lambda *args: RetrievalAgentResponse(sources=[source], parsed_text_by_source={source.id: text}))
    class Provider(ResearchTool):
        tool_name = "synthetic discovery"
        origin = "synthetic discovery"
        def _search(self, request):
            return [source], 1, "https://synthetic.invalid", "{}"
    response = DeepResearchWorkflow().execute(DeepResearchRequest(project=project, user_request="Synthetic source",
                          providers=[Provider()], verification_engine=synthetic_verifier, min_sources=1, generate_docx=False))
    candidates = read_jsonl(project.directory / "evidence.jsonl")
    assert candidates, response.error_message
    assert all((e["reading_depth"] == "FULL_TEXT") is (kind == "examined") and e["evidence_type"] == "BACKGROUND" and e["strength"] == "WEAK" and e["confidence"] <= .2 for e in candidates)
    if kind in {"partial", "quote_failure"}:
        assert not any(e["quote_verified"] for e in candidates)
    assert ReviewQueue.load(project.directory / "review_queue.json").blocking_items()
    assert response.metadata["finalization_allowed"] is False


def pdf_bytes(text=None):
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    if text is not None:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 20 250 Td (" + text + ") Tj ET").encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("direct", [True, False])
def test_new_empty_pdf_cannot_reuse_old_parse_metadata(tmp_path, direct):
    project = project_at(tmp_path / "project")
    source = Source(title="Synthetic book", source_type=SourceType.BOOK, state=SourceState.METADATA_VERIFIED,
                    access_mode=AccessMode.OPEN_DOWNLOAD, rights_status=RightsStatus.OPEN_LICENSE,
                    url="https://synthetic.invalid/book.pdf", download_urls=["https://synthetic.invalid/book.pdf"])
    payloads = iter([pdf_bytes("Readable synthetic book text."), pdf_bytes()])
    tool = RetrievalTool(fetcher=lambda *args: RetrievedPayload(next(payloads), "application/pdf"))
    request = RetrievalRequest(project=project, source=source, direct_download=direct, allow_direct_download=direct, allow_overwrite=True)
    first = tool.execute(request)
    assert first.success and source.metadata["pdf_pages"] and source.metadata["parsed_readable"]
    original = Path(first.document_path).read_bytes()
    second = tool.execute(request)
    assert source.metadata["pdf_pages"] == []
    assert source.metadata["unreadable_pages"] == []
    assert source.metadata["parsed_readable"] is False
    assert source.metadata["content_verification"]["full_text"] is False
    assert not second.success and "0 pages" in second.error_message
    assert Path(first.document_path).read_bytes() == original


def test_zero_page_pdf_is_failure():
    result = PDFParserTool().parse(pdf_bytes())
    assert not result.success and "0 pages" in result.error_message


@pytest.mark.parametrize("source_type,full_html,open_rights,expected", [
    (SourceType.WEB_RESOURCE, True, True, True),
    (SourceType.WEB_RESOURCE, False, True, False),
    (SourceType.WEB_RESOURCE, True, False, False),
    (SourceType.BOOK, True, True, False),
    (SourceType.BOOK_CHAPTER, True, True, False),
])
def test_html_contract_preserves_book_and_rights_guards(tmp_path, source_type, full_html, open_rights, expected):
    project = project_at(tmp_path / "project")
    source = Source(title="Synthetic web document", source_type=source_type, state=SourceState.METADATA_VERIFIED,
                    url="https://synthetic.invalid/document", access_mode=AccessMode.READ_ONLINE,
                    rights_status=RightsStatus.OPEN_LICENSE if open_rights else RightsStatus.UNKNOWN)
    html = "<h1>Synthetic web document</h1><p>A synthetic landing page description.</p>"
    if full_html:
        html += "<h2>Methods</h2><p>Dummy methods.</p><h2>Results</h2><p>Dummy results.</p><h2>Discussion</h2><p>Dummy discussion.</p><h2>References</h2><p>Dummy reference.</p>"
    source.metadata.update(pdf_pages=[{"page": 99, "text": "stale"}], parsed_readable=True)
    tool = RetrievalTool(fetcher=lambda *args: RetrievedPayload(html.encode(), "text/html"))
    response = tool.execute(RetrievalRequest(project=project, source=source, allow_direct_download=False))
    assert response.success
    assert source.metadata["content_verification"]["full_text"] is expected
    assert source.metadata["pdf_pages"] == []
    assert source.metadata["unreadable_pages"] == []
    assert source.metadata["parsed_readable"] is True
