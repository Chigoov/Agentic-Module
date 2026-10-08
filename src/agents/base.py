"""Base agent interface.

Specification anchors:
  * ARCHITECTURE.md §2 — agents are reasoning, tools are capabilities.
  * 00_MASTER_INSTRUCTION.md §6 — "An agent performs a multi-step reasoning or
    decision-making task."
  * AGENT_CONSTITUTION.md §11 — agents must request human review when they
    encounter ambiguity that affects correctness or when task constraints make
    a fully correct outcome impossible.

An agent coordinates tools, interprets results, and makes decisions. Unlike
tools (which are stateless single-shot operations), agents can maintain state
across multiple invocations, request clarification, and escalate to human review.

Phase 1 creates only the interface; agent implementations arrive in Phase 3+.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from src.core.errors import HumanReviewRequired
from src.core.logging import get_logger
from src.runtime.progress import progress_context, progress_scope, record_progress

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "BaseAgent",
]


class AgentRequest(BaseModel):
    """Base contract for agent input."""

    model_config = ConfigDict(extra="forbid")


class AgentResponse(BaseModel):
    """Base contract for agent output.

    Attributes
    ----------
    success:
        Whether the agent completed its task.
    needs_human_review:
        Whether the agent is escalating a decision to the user
        (AGENT_CONSTITUTION.md §11).
    review_prompt:
        Structured question when ``needs_human_review`` is ``True``, formatted
        per WORKFLOW.md §3.
    output:
        The agent's work product when ``success`` is ``True``.
    error_message:
        Explanation when ``success`` is ``False``.
    metadata:
        Diagnostic information for auditability.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    needs_human_review: bool = False
    review_prompt: str | None = None
    output: Any = None
    error_message: str | None = None
    metadata: dict[str, Any] = {}


TRequest = TypeVar("TRequest", bound=AgentRequest)
TResponse = TypeVar("TResponse", bound=AgentResponse)


class BaseAgent(ABC, Generic[TRequest, TResponse]):
    """Abstract base for every agent in the system.

    Agents differ from tools in that they are stateful, iterative, and
    decision-making. A tool transforms input to output; an agent decides *which*
    tools to call, interprets their responses, and requests clarification when
    needed.
    """

    #: Human-readable agent name for logs and audit reports.
    agent_name: str = ""

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or self.agent_name or type(self).__name__
        self._logger = get_logger(f"agents.{self.name}")

    def execute(self, request: TRequest) -> TResponse:
        """Publish real lifecycle events for CLI and API callers alike."""
        root_job = not progress_context()
        project = getattr(request, "project", None)
        fields = {"agent_id": self.name}
        if project is not None:
            fields.update(project_path=str(project.directory), project_name=project.title or project.name)
        with progress_scope(**fields):
            kind = "job" if root_job else "agent"
            self._progress("running", kind)
            response = self._execute_logged(request)
            status = str(response.metadata.get("result_status") or "").lower()
            if status not in {"partial", "failed", "blocked"}:
                status = "partial" if response.needs_human_review or getattr(response, "failed", []) else "completed" if response.success else "failed"
            counts = {}
            if hasattr(response, "parsed_text_by_source"):
                counts["retrieved"] = len(response.parsed_text_by_source)
            self._progress(status, kind, result_status=response.metadata.get("result_status"),
                run_id=getattr(response, "run_id", None), finalization_allowed=response.metadata.get("finalization_allowed"), **counts)
            return response

    def _progress(self, status: str, kind: str, **extra: Any) -> None:
        try:
            record_progress(self.name, status, message=self.name, event_kind=kind, **extra)
        except (OSError, ValueError) as exc:
            self._logger.warning("Progress unavailable", extra={"error": str(exc)})

    def _execute_logged(self, request: TRequest) -> TResponse:
        """Public entry point: log, invoke, and capture unhandled errors.

        Returns
        -------
        TResponse
            The agent's response. Check ``success`` before using ``output``.
        """
        self._logger.info("Agent invoked", extra={"agent": self.name})
        try:
            response = self._execute(request)
        except HumanReviewRequired as exc:
            self._logger.warning(
                "Agent escalated to human review",
                extra={"agent": self.name, "issue": exc.issue},
            )
            response = self._make_error_response(  # type: ignore[assignment]
                error_message=str(exc),
                needs_human_review=True,
                review_prompt=exc.render(),
            )
            response.needs_human_review = True
            response.review_prompt = exc.render()
            response.error_message = str(exc)
        except Exception as exc:
            self._logger.error(
                "Agent raised an unhandled exception",
                extra={"agent": self.name, "error": str(exc)},
                exc_info=True,
            )
            # Type-ignore because the concrete response type may have required
            # fields beyond these. Subclasses that need more must override this.
            response = self._make_error_response(  # type: ignore[assignment]
                error_message=f"{self.name} raised an unhandled exception: {exc}"
            )
            response.metadata["execution_success"] = False
            response.metadata["result_status"] = "FAILED"
            response.metadata["finalization_allowed"] = False

        self._logger.info(
            "Agent completed",
            extra={
                "agent": self.name,
                "success": response.success,
                "needs_review": response.needs_human_review,
            },
        )
        return response

    @abstractmethod
    def _execute(self, request: TRequest) -> TResponse:
        """Subclass implementation of the agent's reasoning and action."""

    def _make_error_response(self, *, error_message: str, **extra: Any) -> TResponse:
        """Construct a failure response. Override if TResponse has required fields."""
        return AgentResponse(  # type: ignore[return-value]
            success=False, error_message=error_message, **extra
        )

    def describe(self) -> dict[str, str]:
        """Diagnostic summary for system health reports."""
        return {
            "agent": self.name,
            "class": type(self).__name__,
        }
