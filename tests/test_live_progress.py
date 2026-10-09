"""Real agent lifecycle and monitor isolation contract."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.paths import ENV_SYSTEM_ROOT, reset_paths_cache
from src.runtime.monitor import create_handler, _jobs
from src.runtime.progress import progress_context, progress_file, read_progress, record_progress


def test_nested_agents_keep_job_identity_and_partial_status(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_SYSTEM_ROOT, str(tmp_path)); reset_paths_cache()

    class Child(BaseAgent):
        agent_name = "retrieval_agent"
        def _execute(self, request):
            record_progress("retrieval", "completed", retrieved=1)
            return AgentResponse(needs_human_review=True)

    class Parent(BaseAgent):
        agent_name = "academic_writing_workflow"
        def _execute(self, request):
            return Child().execute(request)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert all(r.needs_human_review for r in pool.map(lambda _: Parent().execute(AgentRequest()), range(2)))
        events = read_progress()
        jobs = {e["job_id"] for e in events}
        assert len(jobs) == 2
        for job in jobs:
            own = [e for e in events if e["job_id"] == job]
            assert [e["event_kind"] for e in own if e.get("event_kind")] == ["job", "agent", "agent", "job"]
            assert own[-1]["status"] == "partial"
            assert own[2]["agent_id"] == "retrieval_agent"
        assert progress_context() == {}
    finally:
        reset_paths_cache()


def test_monitor_filters_before_limit_and_ignores_unfinished_append(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_SYSTEM_ROOT, str(tmp_path)); reset_paths_cache()
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler())
    thread = threading.Thread(target=server.serve_forever); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        record_progress("retrieval", "completed", job_id="first", retrieved=1)
        for _ in range(1100):
            record_progress("other", "running", job_id="second")
        with progress_file().open("a", encoding="utf-8") as stream:
            stream.write('{"time":')
        with urlopen(base + "/api/progress?job_id=first") as response:
            data = json.load(response)
        assert len(data["events"]) == 1
        assert data["events"][0]["retrieved"] == 1
        for route, content_type in [("/", "text/html"), ("/workflow", "text/html"), ("/assets/office.js", "text/javascript"), ("/assets/research-office.jpg", "image/jpeg"), ("/assets/research-team.webp", "image/webp")]:
            with urlopen(base + route) as response:
                assert response.headers.get_content_type() == content_type
                assert response.read()
    finally:
        server.shutdown(); thread.join(timeout=5); server.server_close(); reset_paths_cache()


def test_home_keeps_jobs_separate_and_does_not_count_finished_agents(tmp_path, monkeypatch):
    (tmp_path / "DATA BASE").mkdir()
    monkeypatch.setenv(ENV_SYSTEM_ROOT, str(tmp_path / "DATA BASE")); reset_paths_cache()
    workspace = tmp_path / "TUGAS 1"
    workspace.mkdir()
    try:
        for job, status in [("live", "running"), ("review", "partial"), ("finished", "completed")]:
            path = str(workspace / job)
            record_progress("academic", "running", job_id=job, project_path=path, event_kind="job", agent_id="coordinator")
            record_progress("retrieval", "running", job_id=job, project_path=path, event_kind="agent", agent_id="reader")
            if status != "running":
                record_progress("academic", status, job_id=job, project_path=path, event_kind="job", agent_id="coordinator")
        record_progress("other", "running", job_id="outside", project_path=str(tmp_path.parent / "outside"), event_kind="job")
        fixture = workspace / "fixture"
        fixture.mkdir()
        (fixture / "project.json").write_text(json.dumps({"origin_project_path": str(tmp_path / "pytest-123" / "source")}), encoding="utf-8")
        record_progress("academic", "running", job_id="fixture", project_path=str(fixture), event_kind="job")
        result = _jobs()
        assert result["counts"] == {"running": 1, "review": 1, "agents": 2}
        assert {j["job_id"] for j in result["jobs"]} == {"live", "review", "finished"}
        assert {j["job_id"]: j["status"] for j in result["jobs"]}["review"] == "partial"
    finally:
        reset_paths_cache()
