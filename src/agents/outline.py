"""Outline agent — builds an evidence-anchored document skeleton.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §22 — ``outline.json`` project artifact.
  * SYSTEM_RULES.md §E.31 — writer works from approved claims only.

This agent turns the set of writable claims into an :class:`~src.schemas.outline.Outline`.
The grouping is deterministic: claims are bucketed by ``section_hint`` (a stable
fallback section for claims without one), and each bucket becomes a top-level
:class:`~src.schemas.outline.OutlineSection` whose ``claim_ids`` pin exactly which
claims the section will state. This is the load-bearing link that lets a later
audit confirm every section's claims are actually supported.

Narrative ordering and section wording (the "thinking" part of outlining) is
deferred to the Model Router; this agent only produces the structural skeleton.
"""

from __future__ import annotations

from collections import OrderedDict

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.schemas.claim import Claim
from src.schemas.outline import Outline, OutlineSection, OutlineStatus
from src.schemas.project import Project
from src.schemas.synthesis import Synthesis

__all__ = [
    "OutlineRequest",
    "OutlineResponse",
    "OutlineAgent",
]

#: Title used for claims that carry no ``section_hint``.
_DEFAULT_SECTION_TITLE = "Temuan"


class OutlineRequest(AgentRequest):
    """Request: build an outline from writable claims and (optional) synthesis."""

    project: Project
    claims: list[Claim] = Field(default_factory=list)
    synthesis: Synthesis | None = None


class OutlineResponse(AgentResponse):
    """The generated outline."""

    outline: Outline | None = None
    section_count: int = 0
    claim_count: int = 0


class OutlineAgent(BaseAgent[OutlineRequest, OutlineResponse]):
    """Assemble writable claims into a deterministic ``Outline``."""

    agent_name = "outline_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> OutlineResponse:
        return OutlineResponse(success=False, error_message=error_message)

    def _execute(self, request: OutlineRequest) -> OutlineResponse:
        writable = [c for c in request.claims if c.is_writable]

        # Bucket claims by section hint, preserving first-seen order; claims
        # without a hint fall into a single trailing section.
        groups: OrderedDict[str, list[Claim]] = OrderedDict()
        for claim in writable:
            key = claim.section_hint or _DEFAULT_SECTION_TITLE
            groups.setdefault(key, []).append(claim)

        sections: list[OutlineSection] = []
        for order, (title, group) in enumerate(groups.items()):
            sections.append(
                OutlineSection(
                    title=title,
                    level=1,
                    claim_ids=[claim.id for claim in group],
                    order=order,
                )
            )

        outline = Outline(
            project_id=request.project.id,
            title=request.project.title or request.project.name,
            sections=sections,
            citation_style=request.project.citation_style,
            language=request.project.language,
            status=OutlineStatus.DRAFT,
        )

        response = OutlineResponse(
            success=True,
            outline=outline,
            section_count=len(sections),
            claim_count=sum(len(section.claim_ids) for section in sections),
        )
        response.metadata = {
            "project_id": request.project.id,
            "writable": len(writable),
            "excluded": len(request.claims) - len(writable),
        }
        return response
