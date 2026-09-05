"""Writer agent — deterministic, evidence-controlled draft assembler.

Specification anchors:
  * SYSTEM_RULES.md §E.31 — writer works from approved claims only.
  * SYSTEM_RULES.md §E.32 — never invent references during writing.
  * SYSTEM_RULES.md §E.39 — every citation maps to a source.
  * AGENT_CONSTITUTION.md §26–§30 — evidence-controlled writing.

The Writer is *not* a model. It assembles a ``draft.md`` skeleton strictly from
writable claims, verified sources, and verbatim evidence that is a citable
quotation. Any claim that is not writable (unsupported / refuted / insufficient)
is excluded and reported — never paraphrased into prose to paper over a gap.

Prose enrichment (turning the skeleton into flowing academic paragraphs) is
deferred to the Model Router, which remains ``PENDING_CONFIGURATION``; the agent
therefore never invents content (AGENT_CONSTITUTION §24).
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.storage import atomic_write_text
from src.schemas.citation import CitationStyle, ReferenceList
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source
from src.tools.citation_manager import CitationManager
from src.tools.reference_formatter import (
    format_in_text_author_year,
    format_reference_list,
)

__all__ = [
    "WriterRequest",
    "WriterResponse",
    "WriterAgent",
]


class WriterRequest(AgentRequest):
    """Request: assemble a draft from an outline, claims, evidence, and sources."""

    project: Project
    outline: Outline
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class WriterResponse(AgentResponse):
    """The assembled draft and its audit surface.

    ``excluded_claims`` are claims the writer refused to include (not writable);
    ``orphan_citations`` are citation keys in the draft that map to no source —
    always empty for the writer's own output, but computed to keep the guard
    honest for the audit phase.
    """

    draft: str = ""
    reference_list: ReferenceList | None = None
    orphan_citations: list[str] = Field(default_factory=list)
    excluded_claims: list[str] = Field(default_factory=list)
    draft_path: str | None = None


class WriterAgent(BaseAgent[WriterRequest, WriterResponse]):
    """Deterministic draft assembler gated on writable claims only."""

    agent_name = "writer_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> WriterResponse:
        return WriterResponse(success=False, error_message=error_message)

    @staticmethod
    def _resolve_style(citation_style: str) -> CitationStyle:
        try:
            return CitationStyle(citation_style)
        except ValueError:
            return CitationStyle.APA7

    def _execute(self, request: WriterRequest) -> WriterResponse:
        writable = [c for c in request.claims if c.is_writable]
        excluded = [c.id for c in request.claims if not c.is_writable]

        source_by_id = {source.id: source for source in request.sources}
        claim_by_id = {claim.id: claim for claim in writable}
        evidence_by_claim: dict[str, list[Evidence]] = defaultdict(list)
        for evidence in request.evidence:
            evidence_by_claim[evidence.claim_id].append(evidence)

        manager = CitationManager()

        # Register only sources that are actually referenced by writable claims.
        for claim in writable:
            for source_id in claim.supporting_sources:
                if source_id in source_by_id:
                    manager.register_source(source_by_id[source_id])
            for evidence in evidence_by_claim.get(claim.id, []):
                if evidence.source_id in source_by_id:
                    manager.register_source(source_by_id[evidence.source_id])

        lines: list[str] = [f"# {request.outline.title}", ""]

        for section in request.outline.sections:
            lines.append(f"{'#' * (section.level + 1)} {section.title}")
            lines.append("")
            for claim_id in section.claim_ids:
                claim = claim_by_id.get(claim_id)
                if claim is None:
                    continue

                statement = claim.claim_text
                if claim.qualifier:
                    statement = f"{statement} ({claim.qualifier})"

                citations = self._citations_for(claim, evidence_by_claim, source_by_id)
                lines.append(f"{statement}{citations}")
                lines.append("")

                for evidence in evidence_by_claim.get(claim.id, []):
                    if not evidence.is_citable_quotation:
                        continue
                    source = source_by_id.get(evidence.source_id)
                    if source is None:
                        continue
                    locator = evidence.location.describe()
                    lines.append(
                        f'> "{evidence.evidence_text}" '
                        f"({format_in_text_author_year(source)}, {locator})"
                    )
                    lines.append("")

        draft = "\n".join(lines)

        style = self._resolve_style(request.project.citation_style)
        reference_list = format_reference_list(
            manager.cited_sources(), style=style, project_id=request.project.id
        )

        orphan_citations = manager.detect_orphan_citations(draft)

        draft_path = request.project.artifact_path(ProjectArtifact.DRAFT)
        atomic_write_text(
            draft_path,
            draft + "\n",
            root=request.project.directory,
            overwrite=True,
        )

        response = WriterResponse(
            success=True,
            draft=draft,
            reference_list=reference_list,
            orphan_citations=orphan_citations,
            excluded_claims=excluded,
            draft_path=str(draft_path),
        )
        response.metadata = {
            "project_id": request.project.id,
            "writable": len(writable),
            "excluded": len(excluded),
            "cited_sources": len(reference_list.entries),
        }
        return response

    @staticmethod
    def _citations_for(
        claim: Claim,
        evidence_by_claim: dict[str, list[Evidence]],
        source_by_id: dict[str, Source],
    ) -> str:
        """Render the in-text author-year pointer for a claim's sources.

        Sources are drawn from the claim's bookkeeping first, falling back to
        supporting evidence; duplicates are removed while preserving order.
        """
        source_ids: list[str] = list(claim.supporting_sources)
        if not source_ids:
            source_ids = [
                e.source_id
                for e in evidence_by_claim.get(claim.id, [])
                if e.is_supporting
            ]

        forms: list[str] = []
        seen: set[str] = set()
        for source_id in source_ids:
            source = source_by_id.get(source_id)
            if source is None or source.id in seen:
                continue
            seen.add(source.id)
            forms.append(format_in_text_author_year(source))

        return f" ({'; '.join(forms)})" if forms else ""
