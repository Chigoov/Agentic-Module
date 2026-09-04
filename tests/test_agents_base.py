"""Smoke tests for the agents layer (R-exec / L4).

These are lightweight structural checks: the built-in :class:`BaseAgent`
machinery (routing, error wrapping, human-review escalation) must behave
correctly without needing any external capability.
"""

from __future__ import annotations

from src.agents.base import AgentRequest, AgentResponse, BaseAgent


def test_base_agent_executes_and_returns_success() -> None:
    """A well-behaved agent returns ``success=True`` and its output."""

    class EchoAgent(BaseAgent[AgentRequest, AgentResponse]):
        def _execute(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(success=True, output="echo")

    agent = EchoAgent(name="echo")
    response = agent.execute(AgentRequest())

    assert response.success is True
    assert response.output == "echo"


def test_base_agent_wraps_unhandled_exceptions() -> None:
    """An agent that raises surfaces a structured failure, not a crash."""

    class BrokenAgent(BaseAgent[AgentRequest, AgentResponse]):
        def _execute(self, request: AgentRequest) -> AgentResponse:
            raise ValueError("boom")

    agent = BrokenAgent(name="broken")
    response = agent.execute(AgentRequest())

    assert response.success is False
    assert "boom" in (response.error_message or "")


def test_base_agent_escalates_to_human_review() -> None:
    """AGENT_CONSTITUTION.md - agents may require human review on ambiguity."""

    class EscalateAgent(BaseAgent[AgentRequest, AgentResponse]):
        def _execute(self, request: AgentRequest) -> AgentResponse:
            response = AgentResponse(success=False)
            response.needs_human_review = True
            response.review_prompt = "Clarify scope before proceeding"
            return response

    agent = EscalateAgent(name="escalate")
    response = agent.execute(AgentRequest())

    assert response.success is False
    assert response.needs_human_review is True
    assert response.review_prompt is not None


def test_base_agent_name_defaults_to_class() -> None:
    """When no name is provided, the agent uses its class name."""

    class NamedAgent(BaseAgent[AgentRequest, AgentResponse]):
        def _execute(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(success=True)

    agent = NamedAgent()
    assert agent.name == "NamedAgent"
