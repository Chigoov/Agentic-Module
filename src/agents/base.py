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

from src.core.logging import get_logger

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
        """Public entry point: log, invoke, and capture unhandled errors.

        Returns
        -------
        TResponse
            The agent's response. Check ``success`` before using ``output``.
        """
        self._logger.info("Agent invoked", extra={"agent": self.name})
        try:
            response = self._execute(request)
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
