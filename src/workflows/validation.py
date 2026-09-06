"""End-to-end validation harness for roadmap Phase 16."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.storage import write_json
from src.schemas.project import Project

__all__ = ["ValidationCase", "EndToEndValidationRequest", "EndToEndValidationResponse", "EndToEndValidator"]

ValidationCase = Callable[[], bool]


class EndToEndValidationRequest(AgentRequest):
    project: Project
    cases: dict[str, ValidationCase] = Field(default_factory=dict)


class EndToEndValidationResponse(AgentResponse):
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    report_path: str | None = None


class EndToEndValidator(BaseAgent[EndToEndValidationRequest, EndToEndValidationResponse]):
    agent_name = "end_to_end_validator"

    def _make_error_response(self, *, error_message: str, **extra: object) -> EndToEndValidationResponse:
        return EndToEndValidationResponse(success=False, error_message=error_message)

    def _execute(self, request: EndToEndValidationRequest) -> EndToEndValidationResponse:
        passed: list[str] = []
        failed: list[str] = []
        for name, case in request.cases.items():
            try:
                (passed if case() else failed).append(name)
            except Exception:
                failed.append(name)

        path = request.project.artifact_path("e2e_validation.json")
        write_json(path, {"passed": passed, "failed": failed}, root=request.project.directory, overwrite=True)
        return EndToEndValidationResponse(
            success=not failed,
            passed=passed,
            failed=failed,
            report_path=str(path),
            error_message=None if not failed else "End-to-end validation failed",
        )
