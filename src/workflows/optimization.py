"""Optimization report workflow for roadmap Phase 17."""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.storage import read_jsonl, write_json
from src.schemas.project import Project

__all__ = ["OptimizationRequest", "OptimizationResponse", "OptimizationWorkflow"]


class OptimizationRequest(AgentRequest):
    project: Project
    telemetry_path: str | None = None


class OptimizationResponse(AgentResponse):
    report: dict[str, object] = Field(default_factory=dict)
    report_path: str | None = None


class OptimizationWorkflow(BaseAgent[OptimizationRequest, OptimizationResponse]):
    agent_name = "optimization_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> OptimizationResponse:
        return OptimizationResponse(success=False, error_message=error_message)

    def _execute(self, request: OptimizationRequest) -> OptimizationResponse:
        telemetry = read_jsonl(request.telemetry_path) if request.telemetry_path else []
        total_tokens = sum(int(item.get("tokens_used") or 0) for item in telemetry)
        failed_runs = [item for item in telemetry if item.get("status") not in {None, "ok", "success", "VERIFIED"}]
        report: dict[str, object] = {
            "telemetry_records": len(telemetry),
            "total_tokens": total_tokens,
            "failed_runs": len(failed_runs),
            "recommendations": [],
        }
        if not telemetry:
            report["recommendations"] = ["Collect routing telemetry before tuning cost or latency."]
        elif failed_runs:
            report["recommendations"] = ["Fix failed routes before optimizing speed or token use."]
        else:
            report["recommendations"] = ["No immediate optimization required."]

        path = request.project.artifact_path("optimization_report.json")
        write_json(path, report, root=request.project.directory, overwrite=True)
        return OptimizationResponse(report=report, report_path=str(path))
