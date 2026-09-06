"""Tests for the local workflow monitor."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from src.core.paths import ENV_SYSTEM_ROOT, reset_paths_cache
from src.runtime.monitor import create_handler


def _get_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - local test server only
        return json.loads(response.read().decode("utf-8"))


def test_monitor_serves_page_and_progress_api(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(ENV_SYSTEM_ROOT, str(tmp_path))
    reset_paths_cache()
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base_url, timeout=5) as response:  # noqa: S310 - local test server only
            assert "AUTONOMI AGENTIC ILMIAH" in response.read().decode("utf-8")

        plan = _get_json(f"{base_url}/api/plan?topic=hak%20anak")
        assert plan["success"] is True
        assert plan["plan"]["citation_style"] == "APA7"

        progress = _get_json(f"{base_url}/api/progress")
        assert progress["success"] is True
        assert len(progress["events"]) >= 2
    finally:
        server.shutdown()
        thread.join(timeout=5)
        reset_paths_cache()
