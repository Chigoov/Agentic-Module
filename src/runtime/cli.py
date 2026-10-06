"""Command-line interface for AI agents and humans."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from src.agents.research import ResearchPlannerAgent, ResearchPlannerRequest, TaskAnalyzerAgent, TaskAnalyzerRequest
from src.core.config import get_config
from src.core.errors import PathSafetyError
from src.core.paths import PathResolutionError, get_paths
from src.core.storage import ensure_within, write_json
from src.runtime.bootstrap import bootstrap, health_check
from src.runtime.monitor import serve
from src.schemas.claim import Claim, SemanticReview
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

__all__ = ["main"]


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _project_from_payload(payload: dict[str, Any]) -> Project:
    paths = get_paths()
    config = get_config()
    allowed_workspaces = {ws.casefold() for ws in config.projects.allowed_workspaces}

    if "project" in payload:
        project = Project.model_validate(payload["project"])
    else:
        raw_path = payload.get("project_path")
        if not raw_path:
            workspace = payload.get("workspace") or config.projects.default_workspace
            project_name = payload.get("project_name") or payload.get("topic") or "academic_project"
            clean_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project_name).strip() or "academic_project"
            ws_dir = paths.workspace_path(workspace, allowed_workspaces=config.projects.allowed_workspaces)
            project_dir = (ws_dir / clean_name).resolve()
        else:
            project_dir = Path(raw_path).expanduser().resolve()

        project = Project(
            name=payload.get("project_name") or project_dir.name,
            workspace=payload.get("workspace", config.projects.default_workspace),
            path=str(project_dir),
            title=payload.get("title") or project_dir.name,
            citation_style=payload.get("citation_style", "APA7"),
            language=payload.get("language", "id"),
            user_request=payload.get("topic", ""),
        )

    # Security boundary validation:
    # 1. Refuse any project inside SYSTEM_ROOT (DATA BASE)
    if paths.is_inside_system_root(project.directory):
        raise PathSafetyError(
            "Project directory cannot be inside SYSTEM_ROOT (DATA BASE)",
            path=str(project.directory),
            root=str(paths.system_root),
        )
    # 2. If inside workspace_root, enforce allowed_workspaces if workspace creation is disabled
    if paths.is_inside_workspace(project.directory):
        if not config.projects.allow_workspace_creation and project.workspace.casefold() not in allowed_workspaces:
            raise PathSafetyError(
                f"Project workspace {project.workspace!r} is not an allowed workspace: {sorted(allowed_workspaces)}",
                path=str(project.directory),
                root=str(paths.workspace_root),
            )

    project.directory.mkdir(parents=True, exist_ok=True)
    return project


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
    semantic_reviews = [
        SemanticReview.model_validate(item)
        for item in payload.get("semantic_reviews", [])
    ]

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
            semantic_reviews=semantic_reviews,
            verification_engine=VerificationEngine(),
            generate_docx=not args.no_docx,
            command="run-academic",
            input_path=args.input_json,
        )
    )
    print(_json(response.model_dump(mode="json")))
    return 0 if response.success else 1


def _cmd_research(args: argparse.Namespace) -> int:
    if args.input_json:
        payload = _read_json(args.input_json)
        project = _project_from_payload(payload)
        user_request = str(payload.get("topic") or payload.get("user_request") or project.user_request or "")
        claims = [Claim.model_validate(item) for item in payload.get("claims", [])]
        evidence = [Evidence.model_validate(item) for item in payload.get("evidence", [])]
        sources = [Source.model_validate(item) for item in payload.get("sources", [])]
        outline = Outline.model_validate(payload["outline"]) if payload.get("outline") else None
        semantic_reviews = [
            SemanticReview.model_validate(item)
            for item in payload.get("semantic_reviews", [])
        ]
    elif args.topic:
        user_request = args.topic.strip()
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_request.lower())[:30].strip("_") or "research_run"
        proj_dir = get_paths().workspace_path(args.workspace) / safe_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        project = Project(
            name=safe_name,
            workspace=args.workspace,
            path=str(proj_dir),
            title=user_request,
            user_request=user_request,
        )
        claims = []
        evidence = []
        sources = []
        outline = None
        semantic_reviews = []
    else:
        print(_json({"success": False, "error": "Either --topic or --input-json must be provided"}), file=sys.stderr)
        return 1

    from src.workflows.deep_research import DeepResearchRequest, DeepResearchWorkflow

    response = DeepResearchWorkflow().execute(
        DeepResearchRequest(
            project=project,
            user_request=user_request,
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
            semantic_reviews=semantic_reviews,
            verification_engine=VerificationEngine(),
            generate_docx=not getattr(args, "no_docx", False),
            min_sources=getattr(args, "min_sources", 2),
            max_sources=getattr(args, "max_sources", 10),
            command="research",
            input_path=getattr(args, "input_json", None),
        )
    )
    print(_json(response.model_dump(mode="json")))
    return 0 if response.success else 1


def _resolve_project_dir(args: argparse.Namespace) -> Path | None:
    target_path: Path | None = None
    explicitly_specified = False

    if getattr(args, "input_json", None):
        explicitly_specified = True
        try:
            payload = _read_json(args.input_json)
            raw_path = payload.get("project", {}).get("path") or payload.get("project_path") or ""
            if raw_path:
                target_path = Path(raw_path).resolve()
        except Exception:
            pass
    elif getattr(args, "project_flag", None) or getattr(args, "project", None):
        proj_str = getattr(args, "project_flag", None) or getattr(args, "project", "")
        if proj_str:
            explicitly_specified = True
            target_path = Path(proj_str).resolve()

    if not explicitly_specified and (target_path is None or not target_path.exists()):
        try:
            paths = get_paths()
            config = get_config()
            for ws in paths.project_workspaces(config.projects.allowed_workspaces):
                candidate_runs = [p for p in ws.glob("*/runs") if p.is_dir() and not paths.is_inside_system_root(p)]
                if candidate_runs:
                    target_path = candidate_runs[0].parent
                    break
        except Exception:
            pass

    if target_path is not None:
        paths = get_paths()
        if paths.is_inside_system_root(target_path):
            return None

    return target_path


def _cmd_runs(args: argparse.Namespace) -> int:
    target_path = _resolve_project_dir(args)
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


def _cmd_export_bundle(args: argparse.Namespace) -> int:
    target_path = _resolve_project_dir(args)
    if target_path is None or not target_path.exists():
        print(_json({"success": False, "error": "Project directory not found"}), file=sys.stderr)
        return 1

    from src.workflows.export_bundle import export_bundle

    result = export_bundle(
        target_path,
        run_id=args.run_id,
        include_failed=getattr(args, "include_failed", False),
    )
    if not result.get("success", False):
        print(_json(result), file=sys.stderr)
        return 1
    print(_json(result))
    return 0


def _cmd_review_queue(args: argparse.Namespace) -> int:
    target_path = _resolve_project_dir(args)
    if target_path is None or not target_path.exists():
        print(_json({"success": False, "error": "Project directory not found"}), file=sys.stderr)
        return 1

    from src.schemas.project import ProjectArtifact
    from src.schemas.review import ReviewQueue

    queue_path = target_path / ProjectArtifact.REVIEW_QUEUE.value
    queue = ReviewQueue.load(queue_path)

    # Resolution mode
    if getattr(args, "resolve", None):
        target_id = args.resolve.strip()
        matched = next((i for i in queue.items if i.id == target_id or i.id.endswith(target_id) or i.item_id == target_id or (target_id in i.reason)), None)
        if not matched:
            print(_json({"success": False, "error": f"Review item '{target_id}' not found in review queue"}), file=sys.stderr)
            return 1

        matched.status = "RESOLVED"
        matched.resolution_notes = getattr(args, "notes", None) or getattr(args, "reason", None) or "Resolved by reviewer"
        queue.save(queue_path, root=target_path)

        # If this review is related to a claim, build/update a SemanticReview
        created_review = None
        claim_id = None
        match_cid = re.search(r"\b(clm_\w+)\b", matched.reason)
        if match_cid:
            claim_id = match_cid.group(1)
        elif matched.item_type == "claim":
            claim_id = matched.item_id

        if claim_id:
            evd_id = None
            src_id = None
            excerpt = None
            loc_str = "abstract"

            # Check fact_audit.json
            fact_path = target_path / ProjectArtifact.FACT_AUDIT.value
            if fact_path.is_file():
                try:
                    fa_data = _read_json(str(fact_path))
                    for asm in fa_data.get("assessments", []):
                        if asm.get("claim_id") == claim_id:
                            evd_id = asm.get("evidence_id")
                            src_id = asm.get("source_id")
                            excerpt = asm.get("evidence_text")
                            loc_str = asm.get("evidence_location") or "abstract"
                            break
                except Exception:
                    pass

            if not evd_id or not src_id or not excerpt:
                # Check citation_map.json
                cmap_path = target_path / ProjectArtifact.CITATION_MAP.value
                if cmap_path.is_file():
                    try:
                        cm_data = _read_json(str(cmap_path))
                        for cit in cm_data.get("citations", []):
                            if cit.get("claim_id") == claim_id and cit.get("evidence_id"):
                                evd_id = cit.get("evidence_id")
                                src_id = cit.get("source_id")
                                loc_str = cit.get("location") or "abstract"
                                break
                    except Exception:
                        pass

            if not excerpt:
                # Check runs snapshot
                runs_dir = target_path / "runs"
                if runs_dir.is_dir():
                    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
                    if run_dirs:
                        evd_snap = run_dirs[0] / "evidence_snapshot.json"
                        if evd_snap.is_file():
                            try:
                                evds = _read_json(str(evd_snap))
                                for ev in evds:
                                    if ev.get("claim_id") == claim_id or ev.get("id") == evd_id:
                                        evd_id = ev.get("id")
                                        src_id = ev.get("source_id")
                                        excerpt = ev.get("evidence_text")
                                        loc_obj = ev.get("location")
                                        if isinstance(loc_obj, dict):
                                            loc_str = loc_obj.get("locator") or (f"p. {loc_obj.get('page')}" if loc_obj.get("page") else "abstract")
                                        break
                            except Exception:
                                pass

            if claim_id and evd_id and src_id and excerpt:
                from src.schemas.claim import SemanticDecision, SemanticReview
                decision_str = getattr(args, "decision", "SUPPORTED") or "SUPPORTED"
                decision = SemanticDecision.SUPPORTED if decision_str.upper() == "SUPPORTED" else SemanticDecision.PARTIALLY_SUPPORTED
                sr = SemanticReview(
                    claim_id=claim_id,
                    decision=decision,
                    reason=getattr(args, "notes", None) or getattr(args, "reason", None) or f"Verified against source {src_id}",
                    evidence_id=evd_id,
                    source_id=src_id,
                    evidence_excerpt=excerpt,
                    location=loc_str,
                    reviewer=getattr(args, "reviewer", "human_expert") or "human_expert",
                    method="expert_semantic_assessment",
                )
                created_review = sr.model_dump(mode="json")
                sem_path = target_path / ProjectArtifact.SEMANTIC_REVIEWS.value
                existing_sem = []
                if sem_path.is_file():
                    try:
                        existing_sem = _read_json(str(sem_path))
                        if not isinstance(existing_sem, list):
                            existing_sem = []
                    except Exception:
                        existing_sem = []
                existing_sem = [r for r in existing_sem if r.get("claim_id") != claim_id]
                existing_sem.append(created_review)
                write_json(sem_path, existing_sem, root=target_path, overwrite=True)

        print(_json({
            "success": True,
            "project_directory": str(target_path),
            "resolved_item": matched.to_dict(),
            "semantic_review": created_review,
            "pending_count": len([i for i in queue.items if i.status == "PENDING"]),
        }))
        return 0

    # Inspection mode
    items = queue.items
    if getattr(args, "status", None):
        items = [i for i in items if i.status == args.status.upper()]
    if getattr(args, "severity", None):
        items = [i for i in items if i.severity == args.severity.upper()]

    print(_json({
        "success": True,
        "project_directory": str(target_path),
        "total_items": len(items),
        "items": [i.to_dict() for i in items],
    }))
    return 0


def _cmd_finalize(args: argparse.Namespace) -> int:
    target_path = _resolve_project_dir(args)
    if target_path is None or not target_path.exists():
        print(_json({"success": False, "error": "Project directory not found"}), file=sys.stderr)
        return 1

    from src.schemas.project import ProjectArtifact
    from src.schemas.review import ReviewQueue
    from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

    queue_path = target_path / ProjectArtifact.REVIEW_QUEUE.value
    queue = ReviewQueue.load(queue_path)
    critical_pending = [i for i in queue.items if i.severity == "CRITICAL" and i.status == "PENDING"]
    if critical_pending:
        print(_json({
            "success": False,
            "error": "Cannot finalize: critical review items remain pending in review queue",
            "pending_critical_items": [i.to_dict() for i in critical_pending],
        }), file=sys.stderr)
        return 1

    project = Project(
        name=target_path.name,
        workspace=target_path.parent.name,
        path=str(target_path),
        title=target_path.name.replace("_", " ").title(),
    )

    sources: list[Source] = []
    vsrc_path = target_path / ProjectArtifact.VERIFIED_SOURCES.value
    if vsrc_path.is_file():
        sources = [Source.model_validate(item) for item in _read_json(str(vsrc_path))]

    claims: list[Claim] = []
    claims_path = target_path / ProjectArtifact.CLAIMS.value
    if claims_path.is_file():
        claims = [Claim.model_validate(item) for item in _read_json(str(claims_path))]
    else:
        runs_dir = target_path / "runs"
        if runs_dir.is_dir():
            run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
            if run_dirs:
                snap = run_dirs[0] / "claims_snapshot.json"
                if snap.is_file():
                    claims = [Claim.model_validate(item) for item in _read_json(str(snap))]

    evidence: list[Evidence] = []
    evd_path = target_path / ProjectArtifact.EVIDENCE.value
    if evd_path.is_file():
        from src.core.storage import read_jsonl
        evidence = [Evidence.model_validate(item) for item in read_jsonl(evd_path)]
    else:
        runs_dir = target_path / "runs"
        if runs_dir.is_dir():
            run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
            if run_dirs:
                snap = run_dirs[0] / "evidence_snapshot.json"
                if snap.is_file():
                    evidence = [Evidence.model_validate(item) for item in _read_json(str(snap))]

    outline = None
    out_path = target_path / ProjectArtifact.OUTLINE.value
    if out_path.is_file():
        raw_out = _read_json(str(out_path))
        if isinstance(raw_out, dict):
            outline = Outline.model_validate(raw_out)
    else:
        runs_dir = target_path / "runs"
        if runs_dir.is_dir():
            run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
            if run_dirs:
                snap = run_dirs[0] / "outline_snapshot.json"
                if snap.is_file():
                    raw_snap = _read_json(str(snap))
                    if isinstance(raw_snap, dict):
                        outline = Outline.model_validate(raw_snap)

    # Semantic reviews loaded from project semantic_reviews.json
    semantic_reviews = []
    sem_path = target_path / ProjectArtifact.SEMANTIC_REVIEWS.value
    if sem_path.is_file():
        try:
            raw_sem = _read_json(str(sem_path))
            if isinstance(raw_sem, list):
                semantic_reviews = [SemanticReview.model_validate(r) for r in raw_sem]
        except Exception:
            pass

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
            semantic_reviews=semantic_reviews,
            verification_engine=VerificationEngine(),
            generate_docx=not getattr(args, "no_docx", False),
            command="finalize",
        )
    )

    print(_json(response.model_dump(mode="json")))
    return 0 if response.success else 1


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

    research = sub.add_parser("research", help="Run end-to-end Deep Research Mode")
    research.add_argument("--topic", help="Research topic or user prompt")
    research.add_argument("--input-json", help="JSON file containing research request")
    research.add_argument("--workspace", default="TUGAS 1")
    research.add_argument("--min-sources", type=int, default=2)
    research.add_argument("--max-sources", type=int, default=10)
    research.add_argument("--no-docx", action="store_true")
    research.set_defaults(func=_cmd_research)

    monitor = sub.add_parser("monitor", help="Run localhost API and workflow monitor")
    monitor.add_argument("--host", default="127.0.0.1")
    monitor.add_argument("--port", type=int, default=8000)
    monitor.set_defaults(func=lambda args: serve(args.host, args.port) or 0)

    runs = sub.add_parser("runs", help="Inspect per-run audit trails for an academic project")
    runs.add_argument("project", nargs="?", default="", help="Project directory path")
    runs.add_argument("--project", dest="project_flag", help="Project directory path flag")
    runs.add_argument("--input-json", help="Input JSON file describing the project")
    runs.add_argument("--run-id", help="Inspect a specific run ID")
    runs.add_argument("--prune", action="store_true", help="Prune older runs keeping only N newest runs")
    runs.add_argument("--keep", type=int, default=None, help="Number of newest runs to keep when pruning (must be > 0)")
    runs.set_defaults(func=_cmd_runs)

    export_bundle = sub.add_parser("export-bundle", help="Export an academic run into a portable .zip archive")
    export_bundle.add_argument("project", nargs="?", default="", help="Project directory path")
    export_bundle.add_argument("--project", dest="project_flag", help="Project directory path flag")
    export_bundle.add_argument("--input-json", help="Input JSON file describing the project")
    export_bundle.add_argument("--run-id", help="Target run ID to export (defaults to latest run)")
    export_bundle.add_argument("--include-failed", action="store_true", help="Allow bundling a failed run (snapshots only)")
    export_bundle.set_defaults(func=_cmd_export_bundle)

    rq = sub.add_parser("review-queue", help="Inspect or resolve review queue items")
    rq.add_argument("project", nargs="?", default="", help="Project directory path")
    rq.add_argument("--project", dest="project_flag", help="Project directory path flag")
    rq.add_argument("--input-json", help="Input JSON file describing the project")
    rq.add_argument("--status", help="Filter by status (PENDING, RESOLVED, etc.)")
    rq.add_argument("--severity", help="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)")
    rq.add_argument("--resolve", help="Review item ID to resolve")
    rq.add_argument("--decision", default="SUPPORTED", help="SemanticDecision (SUPPORTED, PARTIALLY_SUPPORTED)")
    rq.add_argument("--notes", help="Resolution notes or review rationale")
    rq.add_argument("--reviewer", default="human_expert", help="Reviewer identity")
    rq.set_defaults(func=_cmd_review_queue)

    finalize = sub.add_parser("finalize", help="Finalize an academic project after resolving review items")
    finalize.add_argument("project", nargs="?", default="", help="Project directory path")
    finalize.add_argument("--project", dest="project_flag", help="Project directory path flag")
    finalize.add_argument("--input-json", help="Input JSON file describing the project")
    finalize.add_argument("--no-docx", action="store_true")
    finalize.set_defaults(func=_cmd_finalize)

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
