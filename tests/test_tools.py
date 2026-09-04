"""Tests for tool and agent interfaces."""

import pytest

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.config import get_config
from src.core.status import IntegrationStatus
from src.tools.base import BaseTool, ToolRequest, ToolResponse
from src.routing.model_router import ModelCapability, ModelRequest, ModelResponse, ModelRouterTool
from src.tools.publish_or_perish import PublishOrPerishRequest, PublishOrPerishResponse, PublishOrPerishTool


def test_publish_or_perish_status_conservative_before_verified() -> None:
    """PublishOrPerishTool.status() stays NOT_IMPLEMENTED until a real test proves it.

    Per SYSTEM_RULES §H.47-49 and the Phase 2 directive #7, the adapter must NOT
    report VERIFIED merely because the executable exists. Only a real runtime
    run that normalized a Source calls mark_verified().
    """
    tool = PublishOrPerishTool()
    # Without a proven real run, status must be conservative (NOT_IMPLEMENTED).
    assert tool.status() is IntegrationStatus.NOT_IMPLEMENTED


def test_publish_or_perish_execute_gated_by_status() -> None:
    """PublishOrPerishTool.execute() is gated: it returns a structured failure
    while status is NOT_IMPLEMENTED, and never fabricates a result."""
    tool = PublishOrPerishTool()
    request = PublishOrPerishRequest(query="test")
    response = tool.execute(request)
    # Because status is NOT_IMPLEMENTED, base execute() refuses to invoke the
    # underlying subprocess and returns a structured, honest failure.
    assert response.success is False
    assert response.error_code == "NOT_IMPLEMENTED"
    assert response.status is IntegrationStatus.NOT_IMPLEMENTED


def test_publish_or_perish_normalize_flattens_dict_authors() -> None:
    """OpenAlex authors are dicts ({name, affiliation}); Crossref are strings.

    _normalize() must flatten both into a list of author-name strings so the
    internal Source shape is consistent regardless of datasource.
    """
    tool = PublishOrPerishTool()
    raw = {
        "title": "ImageNet classification",
        "authors": [
            {"name": "Alex Krizhevsky", "affiliation": "Google"},
            {"name": "Ilya Sutskever", "affiliation": "Google"},
        ],
        "year": 2012,
    }
    normalized = tool._normalize(raw)
    assert normalized["authors"] == ["Alex Krizhevsky", "Ilya Sutskever"]


def test_publish_or_perish_normalize_keeps_string_authors() -> None:
    """Crossref authors are plain strings; _normalize() must keep them."""
    tool = PublishOrPerishTool()
    raw = {"title": "A paper", "authors": ["Geoffrey Hinton", "Yann LeCun"]}
    normalized = tool._normalize(raw)
    assert normalized["authors"] == ["Geoffrey Hinton", "Yann LeCun"]


def test_publish_or_perish_capability_matrix_is_granular() -> None:
    """Phase 2.1 directive §4: no single global VERIFIED label.

    The capability matrix must report per-dimension status so the system never
    implies every PoP capability is verified when only Crossref is proven.
    """
    tool = PublishOrPerishTool()
    matrix = tool.capability_matrix()
    # The six required dimensions (Phase 2.1 directive §4).
    for dim in (
        "tool_availability",
        "cli_availability",
        "datasource_crossref",
        "query_field_title",
        "output_availability",
        "normalization_availability",
    ):
        assert dim in matrix
        assert matrix[dim]["status"] == "VERIFIED"
    # Honest non-verified dimensions: OpenAlex/SemanticScholar are only partial.
    assert matrix["datasource_openalex"]["status"] == "PARTIALLY_VERIFIED"
    assert matrix["datasource_semantic_scholar"]["status"] == "PARTIALLY_VERIFIED"
    # Credential-gated sources must NOT be VERIFIED.
    assert matrix["datasource_scopus"]["status"] == "PENDING_CONFIGURATION"
    assert matrix["datasource_wos"]["status"] == "PENDING_CONFIGURATION"
    assert matrix["datasource_google_scholar"]["status"] == "UNAVAILABLE"


def test_model_router_status_pending_configuration() -> None:
    """ModelRouterTool reports PENDING_CONFIGURATION status."""
    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.PENDING_CONFIGURATION


def test_model_router_execute_returns_failure() -> None:
    """ModelRouterTool.execute() returns a failure response when unconfigured."""
    tool = ModelRouterTool()
    request = ModelRequest(
        prompt="test prompt",
        capability=ModelCapability.REASONING,
    )
    response = tool.execute(request)
    assert response.success is False
    assert response.error_code == "PENDING_CONFIGURATION"
    assert response.status is IntegrationStatus.PENDING_CONFIGURATION


def test_base_agent_needs_review_escalation() -> None:
    """BaseAgent can signal that it needs human review."""
    
    class TestAgent(BaseAgent[AgentRequest, AgentResponse]):
        """Test agent that always escalates."""
        
        def _execute(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(
                success=False,
                needs_human_review=True,
                review_prompt="Test escalation: need guidance on approach",
            )
    
    agent = TestAgent()
    request = AgentRequest()
    response = agent.execute(request)
    
    assert response.success is False
    assert response.needs_human_review is True
    assert "Test escalation" in response.review_prompt
