"""Localhost API and animated workflow monitor."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.agents.research import ResearchPlannerAgent, ResearchPlannerRequest, TaskAnalyzerAgent, TaskAnalyzerRequest
from src.runtime.bootstrap import health_check
from src.runtime.progress import read_progress, record_progress
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

__all__ = ["create_handler", "serve"]


INDEX = """<!doctype html>
<meta charset="utf-8">
<title>Autonomi Monitor</title>
<style>
body{margin:0;background:#0b0f14;color:#e6edf3;font:14px Segoe UI,Arial,sans-serif}
main{max-width:920px;margin:36px auto;padding:0 20px}
h1{font-size:24px;margin:0 0 4px}.sub{color:#8b949e;margin-bottom:28px}
.bar{height:8px;background:#1f2937;border-radius:999px;overflow:hidden;margin:14px 0 28px}
.bar span{display:block;height:100%;width:0;background:linear-gradient(90deg,#2dd4bf,#60a5fa,#a78bfa);animation:pulse 2s ease-in-out infinite}
.row{display:grid;grid-template-columns:120px 120px 1fr 190px;gap:12px;align-items:center;padding:14px 0;border-bottom:1px solid #1f2937}
.dot{width:12px;height:12px;border-radius:50%;background:#6b7280;box-shadow:0 0 0 0 transparent}
.ok .dot{background:#22c55e}.running .dot{background:#60a5fa;animation:ring 1.2s infinite}.failed .dot{background:#ef4444}
.stage{font-weight:600}.status{color:#c9d1d9;text-transform:uppercase;font-size:12px}.time{color:#8b949e;font-size:12px}.empty{color:#8b949e;padding:28px 0}
@keyframes ring{50%{box-shadow:0 0 0 8px rgba(96,165,250,.16)}}@keyframes pulse{50%{width:100%}}
</style>
<main>
  <h1>AUTONOMI AGENTIC ILMIAH</h1>
  <div class="sub">Local workflow monitor</div>
  <div class="bar"><span></span></div>
  <div id="events" class="empty">Menunggu progress...</div>
</main>
<script>
const box=document.getElementById("events");
function cls(s){s=(s||"").toLowerCase();return s.includes("fail")?"failed":s.includes("run")||s.includes("start")?"running":"ok"}
async function load(){
  const r=await fetch("/api/progress");
  const data=await r.json();
  if(!data.events.length){box.className="empty";box.textContent="Menunggu progress...";return}
  box.className="";
  box.innerHTML=data.events.slice().reverse().map(e=>`<div class="row ${cls(e.status)}"><div><span class="dot"></span></div><div class="stage">${e.stage}</div><div><div class="status">${e.status}</div><div>${e.message||""}</div></div><div class="time">${e.time||""}</div></div>`).join("");
}
load(); setInterval(load,2000);
</script>
"""


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _project_from_payload(payload: dict[str, Any]) -> Project:
    if "project" in payload:
        return Project.model_validate(payload["project"])
    project_path = Path(payload["project_path"]).expanduser().resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    return Project(
        name=payload.get("project_name") or project_path.name,
        workspace=payload.get("workspace", "TUGAS 1"),
        path=str(project_path),
        title=payload.get("title") or project_path.name,
        citation_style=payload.get("citation_style", "APA7"),
        language=payload.get("language", "id"),
        user_request=payload.get("topic", ""),
    )


def _plan(topic: str, workspace: str = "TUGAS 1") -> dict[str, Any]:
    task_response = TaskAnalyzerAgent().execute(TaskAnalyzerRequest(user_request=topic, workspace=workspace))
    if not task_response.success or task_response.task is None:
        return {"success": False, "error": task_response.error_message}
    plan = ResearchPlannerAgent().execute(
        ResearchPlannerRequest(task=task_response.task, keywords=task_response.keywords)
    ).plan
    return {"success": True, "task": task_response.task.to_dict(), "keywords": task_response.keywords, "plan": plan}


class MonitorHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str | bytes, content_type: str) -> None:
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, status: int, payload: Any) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, default=str), "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, INDEX, "text/html; charset=utf-8")
        elif parsed.path == "/api/progress":
            self._json(200, {"success": True, "events": read_progress()})
        elif parsed.path == "/api/check":
            record_progress("check", "running", message="Health check started")
            ok = health_check(verbose=False)
            record_progress("check", "success" if ok else "failed", message="Health check completed")
            self._json(200 if ok else 500, {"success": ok})
        elif parsed.path == "/api/plan":
            query = parse_qs(parsed.query)
            topic = query.get("topic", [""])[0]
            workspace = query.get("workspace", ["TUGAS 1"])[0]
            record_progress("plan", "running", message=topic)
            payload = _plan(topic, workspace)
            record_progress("plan", "success" if payload["success"] else "failed", message="Plan completed")
            self._json(200 if payload["success"] else 500, payload)
        else:
            self._json(404, {"success": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run-academic":
            self._json(404, {"success": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        record_progress("academic", "running", message="Academic workflow started")
        project = _project_from_payload(payload)
        response = AcademicWritingWorkflow().execute(
            AcademicWritingRequest(
                project=project,
                claims=[Claim.model_validate(x) for x in payload.get("claims", [])],
                evidence=[Evidence.model_validate(x) for x in payload.get("evidence", [])],
                sources=[Source.model_validate(x) for x in payload.get("sources", [])],
                outline=Outline.model_validate(payload["outline"]) if payload.get("outline") else None,
            )
        )
        record_progress("academic", "success" if response.success else "failed", message=response.error_message or "Academic workflow completed")
        self._json(200 if response.success else 400, response.model_dump(mode="json"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_handler() -> type[MonitorHandler]:
    return MonitorHandler


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), create_handler())
    print(_json({"success": True, "url": f"http://{host}:{port}"}))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(_json({"success": True, "stopped": True}))
    finally:
        server.server_close()
