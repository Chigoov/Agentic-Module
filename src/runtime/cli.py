"""Command-line interface for AI agents and humans."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from src.agents.research import ResearchPlannerAgent, ResearchPlannerRequest, TaskAnalyzerAgent, TaskAnalyzerRequest
from src.core.paths import PathResolutionError, get_paths
from src.core.storage import ensure_within
from src.runtime.bootstrap import bootstrap, health_check
from src.runtime.monitor import serve
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

__all__ = ["main"]


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def _cmd_check(_args: argparse.Namespace) -> int:
    try:
        paths = get_paths()
    except PathResolutionError as exc:
        print(_json({"success": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0 if health_check(paths=paths, verbose=True) else 1


def _cmd_plan(args: argparse.Namespace) -> int:
    user_request = args.input
    if args.input_json:
        payload = _read_json(args.input_json)
        user_request = str(payload.get("topic") or payload.get("user_request") or "")
    task_response = TaskAnalyzerAgent().execute(TaskAnalyzerRequest(user_request=user_request, workspace=args.workspace))
    if not task_response.success or task_response.task is None:
        print(_json({"success": False, "error": task_response.error_message}), file=sys.stderr)
        return 1
    plan = ResearchPlannerAgent().execute(
        ResearchPlannerRequest(task=task_response.task, keywords=task_response.keywords)
    ).plan
    print(_json({"success": True, "task": task_response.task.to_dict(), "keywords": task_response.keywords, "plan": plan}))
    return 0


def _cmd_run_academic(args: argparse.Namespace) -> int:
    payload = _read_json(args.input_json)
    project = _project_from_payload(payload)
    claims = [Claim.model_validate(item) for item in payload.get("claims", [])]
    evidence = [Evidence.model_validate(item) for item in payload.get("evidence", [])]
    sources = [Source.model_validate(item) for item in payload.get("sources", [])]
    outline = Outline.model_validate(payload["outline"]) if payload.get("outline") else None

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
            generate_docx=not args.no_docx,
            command="run-academic",
            input_path=args.input_json,
        )
    )
    print(_json(response.model_dump(mode="json")))
    return 0 if response.success else 1


def _cmd_runs(args: argparse.Namespace) -> int:
    target_path: Path | None = None
    if args.input_json:
        try:
            payload = _read_json(args.input_json)
            raw_path = payload.get("project", {}).get("path") or payload.get("project_path") or ""
            if raw_path:
                target_path = Path(raw_path).resolve()
        except Exception:
            pass
    elif args.project:
        target_path = Path(args.project).resolve()

    if target_path is None or not target_path.exists():
        try:
            ws_root = get_paths().workspace_root
            candidate_runs = list(ws_root.glob("**/runs"))
            if candidate_runs:
                target_path = candidate_runs[0].parent
        except Exception:
            pass

    if target_path is None or not target_path.exists():
        print(_json({"success": False, "error": "Project directory with runs/ not found"}), file=sys.stderr)
        return 1

    runs_dir = target_path / "runs" if target_path.name != "runs" else target_path
    if not runs_dir.exists():
        if getattr(args, "prune", False):
            if getattr(args, "keep", None) is None or args.keep <= 0:
                print(
                    _json({"success": False, "error": "--keep must be a positive integer when --prune is specified"}),
                    file=sys.stderr,
                )
                return 1
            print(_json({
                "success": True,
                "project_directory": str(target_path),
                "total_before": 0,
                "kept": 0,
                "deleted": 0,
                "deleted_run_ids": [],
            }))
            return 0
        print(_json({"success": True, "project_directory": str(target_path), "total_runs": 0, "runs": []}))
        return 0

    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]

    # Collect metadata for sorting (newest first)
    runs_with_meta: list[tuple[Path, str, dict[str, Any] | None]] = []
    for d in run_dirs:
        summary_file = d / "run_summary.json"
        summary_data: dict[str, Any] | None = None
        started_at = d.name
        if summary_file.exists():
            try:
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                started_at = str(summary_data.get("started_at") or d.name)
            except Exception:
                pass
        runs_with_meta.append((d, started_at, summary_data))

    runs_with_meta.sort(key=lambda x: x[1], reverse=True)

    if getattr(args, "prune", False):
        if getattr(args, "keep", None) is None or args.keep <= 0:
            print(
                _json({"success": False, "error": "--keep must be a positive integer when --prune is specified"}),
                file=sys.stderr,
            )
            return 1

        total_before = len(runs_with_meta)
        to_delete = runs_with_meta[args.keep:]
        deleted_ids: list[str] = []

        for r_dir, _, _ in to_delete:
            safe_dir = ensure_within(r_dir, runs_dir)
            if safe_dir.resolve() == runs_dir.resolve():
                print(_json({"success": False, "error": "Refusing to delete runs directory itself"}), file=sys.stderr)
                return 1
            shutil.rmtree(safe_dir)
            deleted_ids.append(r_dir.name)

        kept_count = total_before - len(deleted_ids)
        print(_json({
            "success": True,
            "project_directory": str(target_path),
            "total_before": total_before,
            "kept": kept_count,
            "deleted": len(deleted_ids),
            "deleted_run_ids": deleted_ids,
        }))
        return 0

    if args.run_id:
        match = next(
            (item for item in runs_with_meta if item[0].name == args.run_id or item[0].name.endswith(args.run_id)),
            None,
        )
        if not match:
            print(_json({"success": False, "error": f"Run {args.run_id} not found"}), file=sys.stderr)
            return 1
        summary = match[2]
        if summary is None:
            summary_file = match[0] / "run_summary.json"
            if not summary_file.exists():
                print(_json({"success": False, "error": f"Run summary not found in {match[0]}"}), file=sys.stderr)
                return 1
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
        print(_json({"success": True, "run": summary}))
        return 0

    summaries = []
    for d, _, summary_data in runs_with_meta:
        if summary_data is not None:
            summaries.append(summary_data)
        else:
            summary_file = d / "run_summary.json"
            if summary_file.exists():
                try:
                    summaries.append(json.loads(summary_file.read_text(encoding="utf-8")))
                except Exception:
                    summaries.append({"run_id": d.name, "success": False, "error_message": "Corrupted summary"})
            else:
                summaries.append({"run_id": d.name, "success": False, "error_message": "Missing summary"})

    print(_json({
        "success": True,
        "project_directory": str(target_path),
        "total_runs": len(summaries),
        "runs": summaries,
    }))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AUTONOMI AGENTIC ILMIAH CLI")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="Run system health check")
    check.set_defaults(func=_cmd_check)

    plan = sub.add_parser("plan", help="Create a research plan from text or JSON")
    plan.add_argument("input", nargs="?", default="", help="Topic or user request")
    plan.add_argument("--input-json", help="JSON file containing topic/user_request")
    plan.add_argument("--workspace", default="TUGAS 1")
    plan.set_defaults(func=_cmd_plan)

    academic = sub.add_parser("run-academic", help="Run Academic Writing Mode from JSON")
    academic.add_argument("--input-json", required=True)
    academic.add_argument("--no-docx", action="store_true")
    academic.set_defaults(func=_cmd_run_academic)

    monitor = sub.add_parser("monitor", help="Run localhost API and workflow monitor")
    monitor.add_argument("--host", default="127.0.0.1")
    monitor.add_argument("--port", type=int, default=8000)
    monitor.set_defaults(func=lambda args: serve(args.host, args.port) or 0)

    runs = sub.add_parser("runs", help="Inspect per-run audit trails for an academic project")
    runs.add_argument("project", nargs="?", default="", help="Project directory path")
    runs.add_argument("--input-json", help="Input JSON file describing the project")
    runs.add_argument("--run-id", help="Inspect a specific run ID")
    runs.add_argument("--prune", action="store_true", help="Prune older runs keeping only N newest runs")
    runs.add_argument("--keep", type=int, default=None, help="Number of newest runs to keep when pruning (must be > 0)")
    runs.set_defaults(func=_cmd_runs)

    parser.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.check:
        return _cmd_check(args)
    if hasattr(args, "func"):
        return args.func(args)
    try:
        bootstrap(verbose=True)
    except RuntimeError as exc:
        print(_json({"success": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0
