"""Audit probes, not production fixes. All test documents are quarantined fixtures.
Run from the repository root: python docs/audit_independen_2026-09-07/reproduce.py
Results describe observed behavior, not academic facts or valid references.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docx import Document
from src.agents.audit import CitationAuditAgent, CitationAuditRequest
from src.agents.research import VerificationAgent, VerificationRequest
from src.context.dry_run import run_dry_run
from src.core.paths import get_paths, reset_paths_cache, SystemPaths
from src.core.project_manager import ProjectManager
from src.core.storage import write_json
from src.runtime.monitor import create_handler
from src.schemas.project import Project
from src.schemas.source import Source
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.tools.crossref import CrossrefTool
from src.tools.research_tool import ResearchRequest
from src.tools.retrieval import RetrievalTool, RetrievalRequest
from src.tools.reference_formatter import format_reference_list, format_in_text_author_year
from src.tools.verification_tool import VerificationEngine
from src.tools.http_client import HttpClient
from src.workflows.academic import AcademicWritingWorkflow, AcademicWritingRequest
from src.workflows.validation import EndToEndValidator, EndToEndValidationRequest

OUT = Path(__file__).resolve().parent
RUN = Path(tempfile.mkdtemp(prefix="autonomi audit fixtures ")).resolve()
results = {"fixture_warning": "NOT ACADEMIC OUTPUT. Adversarial fixtures only.", "temporary_directory": str(RUN)}

def project(name):
    path = RUN / name
    path.mkdir(parents=True, exist_ok=True)
    return Project(name=name, workspace="audit", path=str(path), title="AUDIT FIXTURE - NOT FOR ACADEMIC USE")

def academic(name, claims=(), sources=(), evidence=()):
    prj = project(name)
    response = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=prj, claims=list(claims), sources=list(sources), evidence=list(evidence)))
    data = response.model_dump(mode="json")
    data["draft"] = (prj.directory / "draft.md").read_text(encoding="utf-8") if (prj.directory / "draft.md").exists() else None
    data["files"] = sorted(p.name for p in prj.directory.iterdir())
    if response.docx_path:
        data["docx_text"] = "\n".join(p.text for p in Document(response.docx_path).paragraphs)
    return data

for name, topic in [("simple", "manfaat membaca untuk mahasiswa"), ("edjust", "PKM-RSH Edjust program pendidikan hak anak remaja 12-18 tahun terdampak perceraian orang tua")]:
    p = subprocess.run([sys.executable, "-m", "src", "plan", topic], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    results["plan_" + name] = {"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}

results["empty_academic"] = academic("empty")
claim = Claim(id="clm_audit", claim_text="AUDIT FIXTURE: unsupported statement", importance=4, status="SUPPORTED", supporting_evidence=["evd_nonexistent"])
results["nonexistent_evidence"] = academic("nonexistent", [claim])
internal = claim.model_copy(update={"claim_text": "AUDIT FIXTURE turn0search0 view0 search0 filecite"})
results["internal_tokens"] = academic("internal", [internal])
source = Source(id="src_audit", title="AUDIT FIXTURE - NOT A REAL SOURCE", doi="NOT_A_DOI_AUDIT", state="REJECTED")
with_source = claim.model_copy(update={"supporting_sources": [source.id]})
results["invalid_doi_rejected_source"] = academic("invalid", [with_source], [source])
results["missing_metadata"] = academic("missing", [with_source], [source.model_copy(update={"doi": None, "state": "DISCOVERED"})])
conflicted = with_source.model_copy(update={"status": "CONFLICTED", "contradicting_evidence": ["evd_against"]})
against = Evidence(id="evd_against", claim_id=claim.id, source_id=source.id, evidence_text="AUDIT FIXTURE contradicts the assertion", relationship="contradicts", verbatim=False)
results["conflict"] = academic("conflict", [conflicted], [source], [against])
quote = Evidence(claim_id=claim.id, source_id=source.id, evidence_text="AUDIT FIXTURE unverified quotation", quote_verified=True, location={"page": 999})
results["asserted_quote_and_page"] = academic("quote", [with_source], [source], [quote])
results["apa_orphan_audit"] = CitationAuditAgent().execute(CitationAuditRequest(project=project("orphan"), draft="AUDIT FIXTURE (Nonexistent, 2024)")).model_dump(mode="json")
repeat = project("repeat")
(repeat.directory / "draft.md").write_text("USER EDIT SENTINEL", encoding="utf-8")
AcademicWritingWorkflow().execute(AcademicWritingRequest(project=repeat))
results["overwrite"] = {"old_draft_preserved": "USER EDIT SENTINEL" in (repeat.directory / "draft.md").read_text(), "backups": [p.name for p in repeat.directory.glob("*.bak")]}
results["empty_validation"] = EndToEndValidator().execute(EndToEndValidationRequest(project=project("validation"))).model_dump(mode="json")
results["public_crossref"] = CrossrefTool().execute(ResearchRequest(query="deep learning", max_results=1)).model_dump(mode="json")
results["default_verification_agent"] = VerificationAgent().execute(VerificationRequest(sources=[Source(title="Deep learning", authors=["LeCun, Y."], year=2015, doi="10.1038/nature14539")])).model_dump(mode="json")
results["context_audit"] = run_dry_run("audit repository").to_dict()

# Live source is retrieved, not fabricated. Altered-title probe is explicitly invalid.
try:
    real = CrossrefTool().lookup_by_doi("10.1038/nature14539")
    assert real is not None
    results["real_source"] = real.model_dump(mode="json")
    real_claim = Claim(claim_text="The retrieved record is titled Deep learning.", supporting_sources=[real.id], status="SUPPORTED")
    results["real_source_formatting"] = academic("real_record", [real_claim], [real])
    changed = real.model_copy(update={"title": "AUDIT FIXTURE unrelated horticulture potatoes", "year": 1900})
    verified = VerificationEngine(providers=[CrossrefTool()]).verify(changed)
    results["real_doi_wrong_metadata"] = {"state": verified.recommended_state, "report": verified.report.model_dump(mode="json")}
except Exception as exc:
    results["live_source_error"] = repr(exc)

same = [Source(title="AUDIT FIXTURE A", authors=["Fixture, A."], year=2024), Source(title="AUDIT FIXTURE B", authors=["Fixture, A."], year=2024)]
results["duplicate_reference_keys"] = {"keys": [e.citation_key for e in format_reference_list(same).entries], "in_text": [format_in_text_author_year(s) for s in same]}

# Project relocation: copy-like manifest retains the old root.
old = project("old")
new = project("new")
write_json(new.directory / "project.json", old, root=RUN)
manager = ProjectManager(paths=SystemPaths(workspace_root=RUN, system_root=ROOT))
loaded = manager.load(workspace=".", name="new")
results["manifest_relocation"] = {"loaded_directory": str(loaded.directory), "expected": str(new.directory)}

# Probe only harmless files inside this audit's own temporary tree.
localfile = RUN / "harmless.txt"
localfile.write_text("AUDIT FILE URI SENTINEL", encoding="utf-8")
retrieved = RetrievalTool().execute(RetrievalRequest(project=project("fileuri"), source=Source(title="AUDIT FIXTURE", url=localfile.as_uri())))
results["file_uri_retrieval"] = {"success": retrieved.success, "parsed_text": retrieved.parsed_text}
abstract = RetrievalTool().execute(RetrievalRequest(project=project("abstract"), source=Source(title="AUDIT FIXTURE", abstract="AUDIT abstract only")))
results["abstract_state"] = {"success": abstract.success, "state": abstract.source.state, "method": abstract.retrieval_method}

# A valid large JSON response must not be truncated before it is parsed.
class LargeResponse:
    headers = {"content-type": "application/json"}
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps({"data": "x" * 210000}).encode()
with patch("urllib.request.urlopen", return_value=LargeResponse()):
    try:
        HttpClient(tool_name="audit").get_json("https://example.invalid/audit")
        results["large_valid_json"] = "accepted"
    except Exception as exc:
        results["large_valid_json"] = str(exc)

try:
    with urlopen("http://127.0.0.1:8000/api/progress", timeout=3) as response:
        data = json.loads(response.read())
        results["existing_monitor"] = {"http": response.status, "event_count": len(data.get("events", [])), "cors": response.headers.get("Access-Control-Allow-Origin")}
except Exception as exc:
    results["existing_monitor"] = {"error": repr(exc)}

# Isolated server, so malformed requests never touch the user's active monitor.
os.environ["AUTONOMI_SYSTEM_ROOT"] = str(RUN)
reset_paths_cache()
class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address): pass
server = QuietServer(("127.0.0.1", 0), create_handler())
thread = threading.Thread(target=server.serve_forever)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"
try:
    payload = {"project_path": str(RUN / "api_arbitrary_root")}
    req = Request(base + "/api/run-academic", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Origin": "https://example.invalid"})
    with urlopen(req, timeout=10) as response:
        results["api_untrusted_origin_write"] = {"http": response.status, "cors": response.headers.get("Access-Control-Allow-Origin"), "response": json.loads(response.read())}
    with urlopen(base + "/api/progress") as response:
        results["api_recorded_stages"] = json.loads(response.read())
    try:
        urlopen(Request(base + "/api/run-academic", data=b"{", headers={"Content-Type": "application/json"}), timeout=3)
    except Exception as exc:
        results["api_malformed_json"] = repr(exc)
finally:
    server.shutdown()
    thread.join(5)
    server.server_close()

OUT.joinpath("probe_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in results.items() if k not in {"real_source", "context_audit"}}, ensure_ascii=False, indent=2, default=str))
