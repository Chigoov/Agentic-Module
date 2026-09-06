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
*{box-sizing:border-box}body{margin:0;background:#11110f;color:#f4f1e8;font:14px Segoe UI,Arial,sans-serif}
main{max-width:1180px;margin:28px auto;padding:0 18px}
header{display:flex;justify-content:space-between;gap:16px;align-items:end;margin-bottom:22px}
h1{font-size:24px;margin:0 0 4px}.sub,.time{color:#a8a29e}.pill{border:1px solid #3f3a34;padding:7px 10px;background:#191814}
.flow{position:relative;display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:28px 42px;margin:20px 0 28px}
.node{position:relative;min-height:96px;border:1px solid #3f3a34;background:#1b1a17;padding:14px;box-shadow:0 0 0 1px rgba(255,255,255,.02),0 14px 28px rgba(0,0,0,.22)}
.node:after{content:"";position:absolute;top:47px;right:-43px;width:42px;height:2px;background:#48433b}
.node:nth-child(5):after,.node:last-child:after{display:none}
.node:nth-child(5){grid-column:5}.node:nth-child(6){grid-column:5}.node:nth-child(6):before{content:"";position:absolute;top:-29px;right:50%;width:2px;height:28px;background:#48433b}
.node:nth-child(n+7):after{right:auto;left:-43px}.node:nth-child(n+7){direction:rtl}.node:nth-child(n+7)>*{direction:ltr}
.icon{width:30px;height:30px;display:grid;place-items:center;margin-bottom:10px;background:#27231d;color:#f5c451;border:1px solid #51483a;font-size:17px}
.title{font-weight:700}.meta{color:#b7b0a6;font-size:12px;margin-top:4px;text-transform:uppercase}.msg{color:#d8d2c7;font-size:12px;margin-top:8px;line-height:1.35}
.node.running{border-color:#36c7b7;box-shadow:0 0 0 1px rgba(54,199,183,.25),0 0 28px rgba(54,199,183,.12)}
.node.success{border-color:#65a765}.node.failed{border-color:#df685d}.node.running .icon{animation:beat 1.1s infinite;background:#18312e;color:#5eead4}
.node.success .icon{background:#20301f;color:#86efac}.node.failed .icon{background:#3a1f1c;color:#fca5a5}
.node.running:after,.node.success:after{background:linear-gradient(90deg,#36c7b7,#f5c451,#36c7b7);background-size:200% 100%;animation:line 1.4s linear infinite}
.events{border-top:1px solid #302c27;padding-top:14px}.row{display:grid;grid-template-columns:110px 105px 1fr 190px;gap:12px;padding:10px 0;border-bottom:1px solid #26231f}.empty{color:#a8a29e;padding:18px 0}
@keyframes beat{50%{transform:scale(1.08);box-shadow:0 0 0 8px rgba(54,199,183,.12)}}@keyframes line{to{background-position:-200% 0}}
@media(max-width:820px){header{display:block}.flow{grid-template-columns:1fr;gap:14px}.node,.node:nth-child(5),.node:nth-child(6){grid-column:auto}.node:after,.node:before{display:none}.row{grid-template-columns:1fr}}
</style>
<main>
  <header>
    <div>
      <h1>AUTONOMI AGENTIC ILMIAH</h1>
      <div class="sub">Live progress agent workflow</div>
    </div>
    <div class="pill">http://127.0.0.1:8000</div>
  </header>
  <section id="flow" class="flow"></section>
  <section class="events">
    <div class="sub">Recent activity</div>
    <div id="events" class="empty">Menunggu progress...</div>
  </section>
</main>
<script>
const steps=[
  ["instruction","Instruksi","Permintaan diterima"],["check","Check","Cek kesehatan sistem"],
  ["plan","Plan","Rencana riset"],["discovery","Discovery","Pencarian sumber"],["verification","Verify","Verifikasi sumber"],
  ["retrieval","Retrieve","Ambil full text"],["evidence","Evidence","Ekstraksi evidence"],["synthesis","Synthesis","Sintesis dan outline"],
  ["audit","Audit","Citation/fact audit"],["academic","DOCX","Draft dan dokumen akhir"]
];
const icons={instruction:"@",check:"✓",plan:"≡",discovery:"⌕",verification:"◇",retrieval:"↓",evidence:"§",synthesis:"✦",audit:"!",academic:"▣"};
const flow=document.getElementById("flow");
const box=document.getElementById("events");
function state(s){s=(s||"").toLowerCase();return s.includes("fail")?"failed":s.includes("run")||s.includes("start")?"running":s.includes("success")?"success":"idle"}
function paintFlow(events){
  const latest={};
  events.forEach(e=>latest[(e.stage||"").toLowerCase()]=e);
  flow.innerHTML=steps.map(([key,title,fallback])=>{
    const e=latest[key]||{};
    const st=state(e.status);
    return `<article class="node ${st}"><div class="icon">${icons[key]}</div><div class="title">${title}</div><div class="meta">${e.status||"waiting"}</div><div class="msg">${e.message||fallback}</div></article>`;
  }).join("");
}
async function load(){
  const r=await fetch("/api/progress");
  const data=await r.json();
  paintFlow(data.events);
  if(!data.events.length){box.className="empty";box.textContent="Menunggu progress...";return}
  box.className="";
  box.innerHTML=data.events.slice().reverse().map(e=>`<div class="row"><div>${e.stage}</div><div>${e.status}</div><div>${e.message||""}</div><div class="time">${e.time||""}</div></div>`).join("");
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
