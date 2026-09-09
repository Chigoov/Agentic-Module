"""Post-fix verification probes (separate from the original audit baseline).
Run from the repository root: python docs/audit_independen_2026-09-07/verify_fixes.py
All fixtures are quarantined test data, NOT academic output. Results are written
to docs/audit_independen_2026-09-07/verifikasi_perbaikan_2026-09-07.json.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.runtime.monitor import create_handler
from src.schemas.claim import Claim, ClaimStatus
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

RUN = Path(tempfile.mkdtemp(prefix="autonomi verify fixtures "))
results = {"fixture_warning": "NOT ACADEMIC OUTPUT. Adversarial fixtures only.", "temporary_directory": str(RUN)}


def project(name):
    path = RUN / name
    path.mkdir(parents=True, exist_ok=True)
    return Project(name=name, workspace="audit", path=str(path), title="AUDIT FIXTURE - NOT FOR ACADEMIC USE")


def academic(name, claims=(), sources=(), evidence=()):
    prj = project(name)
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(project=prj, claims=list(claims), sources=list(sources), evidence=list(evidence))
    )
    data = response.model_dump(mode="json")
    data["files"] = sorted(p.name for p in prj.directory.iterdir())
    return data


# A01: nonexistent evidence ID must now be rejected by the public workflow.
claim = Claim(id="clm_audit", claim_text="AUDIT FIXTURE: unsupported statement", importance=4,
              status="SUPPORTED", supporting_evidence=["evd_nonexistent"])
results["nonexistent_evidence"] = academic("nonexistent", [claim])

# A02: internal tokens must now be rejected.
internal = claim.model_copy(update={"claim_text": "AUDIT FIXTURE turn0search0 view0 search0 filecite",
                                    "supporting_evidence": []})
results["internal_tokens"] = academic("internal", [internal])

# A02 (author-year orphan): citation with no source must now be rejected.
orphan = claim.model_copy(update={"claim_text": "AUDIT FIXTURE (Nonexistent, 2024).",
                                  "supporting_evidence": []})
results["author_year_orphan"] = academic("orphan", [orphan])

# A04: conflicted claim without disclosure must now be rejected.
conflicted = claim.model_copy(update={"status": "CONFLICTED"})
results["conflict_undisclosed"] = academic("conflict", [conflicted])

# A05: rerun must preserve a manual sentinel edit as a unique backup.
repeat = project("repeat")
(repeat.directory / "draft.md").write_text("USER EDIT SENTINEL", encoding="utf-8")
AcademicWritingWorkflow().execute(AcademicWritingRequest(project=repeat))
backups = [p.name for p in repeat.directory.glob("draft.md.*.bak")]
sentinel_preserved = any(
    "USER EDIT SENTINEL" in (repeat.directory / b).read_text(encoding="utf-8") for b in backups
)
results["overwrite"] = {"old_draft_preserved": sentinel_preserved, "backups": backups}

# A03: DOI with a materially wrong title must no longer be DOI_VERIFIED.
class _Provider:
    name = "probe_provider"
    def lookup_by_doi(self, doi):
        return Source(title="Deep learning", doi=doi)
    def lookup_by_bibliographic(self, title, authors=None, year=None):
        return None

engine = VerificationEngine(providers=[_Provider()], match_threshold=0.6, min_providers=1)
changed = Source(title="AUDIT FIXTURE unrelated horticulture potatoes", authors=["X"], year=1900,
                 doi="10.1038/nature14539")
verified = engine.verify(changed)
results["real_doi_wrong_metadata"] = {"state": verified.recommended_state.value,
                                      "ratio": verified.report.metadata_match_ratio}

# Positive control: a legitimate bundle must still produce draft + DOCX.
src = Source(title="Attention is all you need", authors=["Vaswani, A."], year=2017,
             state=SourceState.APPROVED)
ok_claim = Claim(claim_text="Transformers rely on attention.", supporting_sources=[src.id],
                 supporting_evidence=["evd_ok"], status="SUPPORTED")
ok_evidence = Evidence(id="evd_ok", claim_id=ok_claim.id, source_id=src.id,
                       evidence_text="Transformers rely on attention.",
                       location=EvidenceLocation(locator="abstract"), quote_verified=True)
ok_outline = Outline(title="Fixture", sections=[OutlineSection(title="Findings", claim_ids=[ok_claim.id])])
positive = academic("positive", [ok_claim], [src], [ok_evidence])
results["positive_control"] = {"success": positive["success"], "files": positive["files"]}

out = Path(__file__).resolve().parent / "verifikasi_perbaikan_2026-09-07.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


# A06/A15: localhost API — foreign origin, missing token, malformed JSON.
# Runs on an isolated ephemeral server so the user's monitor is never touched.
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from src.core.paths import reset_paths_cache

os.environ["AUTONOMI_SYSTEM_ROOT"] = str(RUN)
os.environ["AUTONOMI_API_TOKEN"] = "verify-token-abcdef"
reset_paths_cache()


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


server = QuietServer(("127.0.0.1", 0), create_handler())
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"
try:
    # Foreign Origin + missing token (audit probe: previously HTTP 200).
    req = Request(base + "/api/run-academic",
                  data=json.dumps({"topic": "AUDIT FIXTURE"}).encode(),
                  headers={"Content-Type": "application/json", "Origin": "https://example.invalid"})
    try:
        with urlopen(req, timeout=10) as response:
            status, body = response.status, json.loads(response.read())
    except HTTPError as exc:
        status, body = exc.code, json.loads(exc.read())
    results["api_untrusted_origin_write"] = {"http": status, "success": body.get("success"),
                                             "error": body.get("error")}

    # Valid token but malformed JSON: structured error instead of dropped connection.
    req = Request(base + "/api/run-academic", data=b"{",
                  headers={"Content-Type": "application/json", "X-Autonomi-Token": "verify-token-abcdef"})
    try:
        with urlopen(req, timeout=5) as response:
            status, body = response.status, json.loads(response.read())
    except HTTPError as exc:
        status, body = exc.code, json.loads(exc.read())
    results["api_malformed_json"] = {"http": status, "error_code": body.get("error_code")}
finally:
    server.shutdown()
    thread.join(5)
    server.server_close()

out = Path(__file__).resolve().parent / "verifikasi_perbaikan_2026-09-07.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
