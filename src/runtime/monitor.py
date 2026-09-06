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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Autonomi Monitor</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#061622;color:#f4fbff;font:14px Segoe UI,Arial,sans-serif;overflow-x:hidden}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(rgba(57,206,255,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(57,206,255,.07) 1px,transparent 1px),radial-gradient(circle at 65% 20%,rgba(255,149,32,.12),transparent 28%);background-size:34px 34px,34px 34px,100% 100%}
main{position:relative;max-width:1540px;margin:0 auto;padding:24px 26px 28px}
header{display:grid;grid-template-columns:1fr 180px 230px 176px;gap:18px;align-items:center;margin-bottom:18px}
h1{font-size:48px;line-height:.96;margin:0;font-weight:900;letter-spacing:0}.accent{color:#31e7ff}.tagline{font-size:24px;color:#baf3ff;margin-top:8px}
.micro{border-left:2px solid #ff9e2b;padding:8px 0 8px 20px;color:#98d8ef;font-size:11px;letter-spacing:4px;line-height:1.7;text-transform:uppercase}.live{justify-self:end;border:1px solid #22c7ff;background:#06273a;padding:12px 18px;color:#5fffe2;font-weight:800;box-shadow:0 0 24px rgba(34,199,255,.2)}
.live:before{content:"";display:inline-block;width:12px;height:12px;margin-right:10px;border-radius:50%;background:#55ff9a;box-shadow:0 0 14px #55ff9a;vertical-align:-1px;animation:blink 1.1s infinite}
.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:18px}.metric,.panel,.node,.orchestrator,.loop{border:1px solid #1d83bb;background:rgba(7,34,54,.78);box-shadow:0 0 18px rgba(37,196,255,.15),inset 0 0 24px rgba(9,95,145,.18)}
.metric{min-height:90px;padding:16px;display:grid;grid-template-columns:44px 1fr;gap:12px;align-items:center}.metric .ico{width:44px;height:44px;display:grid;place-items:center;background:#0b3756;border:1px solid #187fbb;color:#42e8ff;font-size:24px}
.metric b{display:block;font-size:18px;color:#67f6ff}.metric span{display:block;color:#b8d5e4;margin-top:5px;font-size:12px}.ring{width:54px;height:54px;border-radius:50%;background:conic-gradient(#24ffe2 var(--p),#18384c 0);display:grid;place-items:center}.ring:after{content:"";width:38px;height:38px;border-radius:50%;background:#092034}
.layout{display:grid;grid-template-columns:1fr 310px;gap:18px}.board{position:relative;min-height:670px;border:1px solid #124c72;background:rgba(4,24,38,.68);padding:18px;overflow:hidden}
.board:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent 0 49%,rgba(255,255,255,.08) 50%,transparent 51%);opacity:.25}
.flow{position:relative;display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:160px 150px 160px;gap:86px 28px;z-index:1}
.node{position:relative;min-height:146px;padding:18px 16px 46px}.node .num{position:absolute;top:12px;left:12px;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#1f8df0;color:white;font-weight:900;font-size:20px}.node .body{margin-left:50px}.title{font-weight:850;font-size:18px}.meta{font-size:12px;margin-top:6px;text-transform:uppercase;color:#a9dcef}.msg{margin-top:12px;color:#def8ff;line-height:1.45}.foot{position:absolute;left:38px;right:38px;bottom:-20px;text-align:center;background:#082943;border:1px solid #1d83bb;padding:8px;color:#9edfff;font-size:12px}
.node:after,.node:before{content:"";position:absolute;background:#33e9ff;box-shadow:0 0 10px #33e9ff}.node:after{top:70px;right:-29px;width:29px;height:3px}.node.down:before{left:50%;bottom:-87px;width:3px;height:87px}.node.left:after{right:auto;left:-29px}.node.no-line:after{display:none}
.s1{border-color:#ff9b28}.s1 .num{background:#ff6a20}.s1:after{background:#ff9b28;box-shadow:0 0 10px #ff9b28}.s2{border-color:#2fc5ff}.s3,.s6{border-color:#21d6a1}.s4,.s8{border-color:#a65cff}.s5{border-color:#44a3ff}.s7{border-color:#f5c451}
.orchestrator{position:absolute;left:50%;top:330px;transform:translate(-50%,-50%);width:330px;min-height:126px;text-align:center;padding:22px;border-color:#ff8a24;box-shadow:0 0 24px rgba(255,138,36,.38),inset 0 0 28px rgba(255,138,36,.12);z-index:2}
.orchestrator .atom{font-size:42px;color:#ffb02e;animation:spin 8s linear infinite}.orchestrator b{display:block;font-size:26px;margin-top:2px}.loop{position:absolute;left:31%;right:28%;bottom:52px;text-align:center;padding:12px;border-color:#ff4dad;color:#ffd5ec;z-index:2}
.panel{padding:16px}.side{display:grid;gap:12px}.panel h2{margin:0 0 14px;font-size:18px}.activity{display:grid;grid-template-columns:54px 1fr 24px;gap:10px;padding:8px 0;border-bottom:1px solid rgba(137,214,255,.14)}.activity .ok{color:#5cff9b}.activity .wait{color:#68869a}
.bars{height:138px;display:flex;align-items:end;gap:6px;border-left:1px solid #2b6f95;border-bottom:1px solid #2b6f95;padding:0 8px 8px}.bars i{flex:1;background:linear-gradient(#30ffe2,#0e5f8f);min-height:8px;animation:grow 2.4s ease-in-out infinite alternate}.output div{padding:9px 0;border-bottom:1px solid rgba(137,214,255,.14)}.empty{color:#9fc7dc;padding:16px 0}
.running{animation:pulse 1.4s infinite}.running .num{background:#28e0c3}.success{box-shadow:0 0 22px rgba(79,255,142,.22),inset 0 0 24px rgba(42,168,92,.18);border-color:#54ee8f}.failed{border-color:#ff625b;box-shadow:0 0 22px rgba(255,98,91,.22)}
@keyframes pulse{50%{box-shadow:0 0 30px rgba(49,231,255,.38),inset 0 0 30px rgba(49,231,255,.16)}}@keyframes blink{50%{opacity:.35}}@keyframes spin{to{transform:rotate(360deg)}}@keyframes grow{to{transform:scaleY(.62)}}@keyframes flow{to{background-position:-200% 0}}
.success:after,.running:after,.success:before,.running:before{background:linear-gradient(90deg,#21ffc8,#ff9b28,#21ffc8);background-size:200% 100%;animation:flow 1.2s linear infinite}
@media(max-width:1px){header,.metrics,.layout{grid-template-columns:1fr}.flow{grid-template-columns:1fr;grid-template-rows:none;gap:14px}.node:after,.node:before,.orchestrator,.loop{display:none}.node{min-height:130px}.foot{position:static;margin:14px 0 -4px}.board{min-height:auto}}
</style>
<main>
  <header>
    <div><h1>Contoh <span class="accent">Agentic AI</span> Sedang Bekerja</h1><div class="tagline">AUTONOMI AGENTIC ILMIAH | Dari prompt pengguna -> analisis -> tool -> proses -> output</div></div>
    <div class="micro">AI bekerja untuk anda<br>mengubah ide menjadi<br>hasil nyata</div>
    <div class="micro">Lebih cerdas<br>lebih cepat<br>masa depan lebih dekat</div>
    <div class="live">LIVE EXECUTION</div>
  </header>
  <section class="metrics">
    <div class="metric"><div class="ring" id="status-ring" style="--p:0%"></div><div>TASK STATUS<b id="task-status">Waiting</b><span>Agent menunggu instruksi...</span></div></div>
    <div class="metric"><div class="ico">[]</div><div>INPUT<b id="input-count">0 prompt</b><span>Teks, web, dokumen</span></div></div>
    <div class="metric"><div class="ico">#</div><div>TOOLS AKTIF<b>Web, Python, API</b><span>Tool lokal terhubung</span></div></div>
    <div class="metric"><div class="ring" id="progress-ring" style="--p:0%"></div><div>PROGRESS<b id="progress">0%</b><span>Memproses...</span></div></div>
    <div class="metric"><div class="ico">@</div><div>OUTPUT TARGET<b>Ringkasan + DOCX</b><span>Format laporan lengkap</span></div></div>
  </section>
  <section class="layout">
    <div class="board">
      <section id="flow" class="flow"></section>
      <div class="orchestrator"><div class="atom">*</div><b>Agent Orchestrator</b><div>Mengkoordinasikan langkah, memilih tool, dan mengelola eksekusi secara otonom</div></div>
      <div class="loop">Feedback Loop: jika perlu, kembali ke perencanaan atau eksekusi untuk hasil lebih baik</div>
    </div>
    <aside class="side">
      <section class="panel"><h2>Aktivitas Langsung <span class="live" style="padding:6px 10px;font-size:12px">LIVE</span></h2><div id="events" class="empty">Menunggu progress...</div></section>
      <section class="panel"><h2>Efisiensi Proses</h2><div class="bars"><i style="height:20%"></i><i style="height:34%"></i><i style="height:30%"></i><i style="height:48%"></i><i style="height:62%"></i><i style="height:78%"></i></div><b id="efficiency">0% saat ini</b></section>
      <section class="panel output"><h2>Output Sedang Disusun...</h2><div id="outputs"></div></section>
    </aside>
  </section>
</main>
<script>
const steps=[
  ["instruction","Input Pengguna","Prompt diterima oleh agent","s1"],["check","Memahami Intent","Cek sistem dan batasan","s2"],
  ["plan","Menyusun Rencana","Rencana eksekusi disusun","s3 down"],["verification","Akses Memori & Konteks","Mengambil konteks relevan","s4 no-line"],
  ["discovery","Pemilihan Tool","Memilih tool yang dibutuhkan","s5"],["retrieval","Eksekusi","Menjalankan tugas secara otonom","s6"],
  ["audit","Validasi","Validasi kualitas output","s7"],["academic","Output Akhir","Hasil siap digunakan","s8 no-line"]
];
const flow=document.getElementById("flow"),box=document.getElementById("events"),outputs=document.getElementById("outputs");
function st(s){s=(s||"").toLowerCase();return s.includes("fail")?"failed":s.includes("run")||s.includes("start")?"running":s.includes("success")?"success":"idle"}
function esc(s){return String(s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function pct(events){const done=new Set(events.filter(e=>st(e.status)==="success").map(e=>(e.stage||"").toLowerCase()));return Math.round(done.size/steps.length*100)}
function paintFlow(events){
  const latest={};events.forEach(e=>latest[(e.stage||"").toLowerCase()]=e);
  flow.innerHTML=steps.map(([key,title,fallback,klass],i)=>{
    const e=latest[key]||{},state=st(e.status),msg=e.message||fallback;
    return `<article class="node ${klass} ${state}"><div class="num">${i+1}</div><div class="body"><div class="title">${title}</div><div class="meta">${esc(e.status||"waiting")}</div><div class="msg">${esc(msg)}</div></div><div class="foot">${esc(fallback)}</div></article>`;
  }).join("");
}
async function load(){
  const r=await fetch("/api/progress"),data=await r.json(),events=data.events||[],progress=pct(events);
  paintFlow(events);
  document.getElementById("progress").textContent=progress+"%";document.getElementById("efficiency").textContent=progress+"% saat ini";
  document.getElementById("progress-ring").style.setProperty("--p",progress+"%");document.getElementById("status-ring").style.setProperty("--p",progress+"%");
  document.getElementById("task-status").textContent=events.some(e=>st(e.status)==="running")?"Running":progress?"Active":"Waiting";
  document.getElementById("input-count").textContent=events.length?events.length+" aktivitas":"0 prompt";
  if(!events.length){box.className="empty";box.textContent="Menunggu progress...";outputs.innerHTML="<div>Menunggu output</div>";return}
  box.className="";
  box.innerHTML=events.slice(-8).reverse().map(e=>`<div class="activity"><span>${esc((e.time||"").slice(11,16))}</span><span>${esc(e.message||e.stage)}</span><b class="${st(e.status)==="success"?"ok":"wait"}">${st(e.status)==="success"?"OK":"o"}</b></div>`).join("");
  outputs.innerHTML=steps.slice(0,4).map(([key,title])=>`<div>${events.some(e=>(e.stage||"").toLowerCase()===key&&st(e.status)==="success")?"OK":".."} ${title}</div>`).join("");
}
load();setInterval(load,2000);
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
