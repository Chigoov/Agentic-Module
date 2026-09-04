"""Shared contracts and base class for the Phase 3 research tools.

Specification anchors:
  * ARCHITECTURE.md §2/§5 — tools are capabilities with a stable interface.
  * PHASE 3 EXECUTION ADDENDUM §4 — granular capability status: a successful
    query for one capability must not mark the whole provider VERIFIED.
  * PHASE 3 EXECUTION ADDENDUM §5 — preserve ``requested_max``, ``raw_count``,
    ``returned_count``, and ``local_truncation`` for providers that ignore limits.

Every HTTP research tool (Crossref, OpenAlex, Semantic Scholar, PubMed) shares a
uniform request/response contract so workflows can treat them interchangeably.
The response preserves both the *requested* limit and the *returned* count, plus
an explicit ``local_truncation`` flag, so the system can report honestly when a
provider ignored ``max_results`` and the adapter had to truncate locally.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from src.core.status import IntegrationStatus
from src.schemas.source import Source
from src.tools.base import BaseTool, ToolRequest, ToolResponse

__all__ = [
    "ResearchRequest",
    "ResearchResponse",
    "ResearchTool",
]


class ResearchRequest(ToolRequest):
    """Uniform input contract for a bibliographic search."""

    query: str = Field(min_length=1)
    year_start: int | None = None
    year_end: int | None = None
    max_results: int = Field(default=25, ge=1, le=200)
    timeout_seconds: int | None = None


class ResearchResponse(ToolResponse):
    """Uniform output contract for a bibliographic search.

    Attributes
    ----------
    results:
        Normalized :class:`Source` records.
    result_count:
        Number of normalized results (after local truncation).
    raw_count:
        Number of raw records parsed from the provider payload.
    requested_max:
        The ``max_results`` the caller requested (Addendum §5).
    returned_count:
        The number of records the provider actually returned before truncation.
    local_truncation:
        ``True`` when the provider ignored the limit and the adapter truncated
        to ``requested_max`` locally (Addendum §5).
    query_used:
        The query string actually sent.
    request_url:
        The final URL (with query string) that was requested.
    raw_response_text:
        Preserved raw body (truncated), for auditability (SYSTEM_RULES §H.50).
    """

    results: list[Source] = Field(default_factory=list)
    result_count: int = 0
    raw_count: int = 0
    requested_max: int = 0
    returned_count: int = 0
    local_truncation: bool = False
    query_used: str = ""
    request_url: str = ""
    raw_response_text: str = ""


class ResearchTool(BaseTool[ResearchRequest, ResearchResponse]):
    """Base class for HTTP research tools with granular, evidence-gated status.

    Subclasses set :attr:`origin` (the provenance label), declare
    :attr:`capabilities` (the granular dimensions), and implement
    :meth:`_search` returning ``(list[Source], raw_count, request_url, raw_text)``.

    ``status()`` stays ``NOT_IMPLEMENTED`` until :meth:`mark_verified` is called
    by a real integration test after a successful run — mirroring the PoP pattern
    (SYSTEM_RULES §H.47-49).
    """

    response_model: ClassVar[type[ToolResponse]] = ResearchResponse

    #: Provenance origin label written onto each Source (e.g. ``"crossref"``).
    origin: ClassVar[str] = ""

    #: Human-readable capability name.
    tool_name: ClassVar[str] = "research"

    #: Granular dimensions, each mapping to an initial (honest) status.
    #: Subclasses override with provider-specific dimensions.
    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_keywords": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    #: Evidence strings recorded alongside each dimension when verified.
    _evidence: ClassVar[dict[str, str]] = {}

    #: Class-level flag set only by mark_verified() after a real, proven run.
    _integration_verified: ClassVar[bool] = False

    # ------------------------------------------------------------------ status
    def status(self) -> IntegrationStatus:
        """Return VERIFIED only after a real run has proven this integration."""
        if self._integration_verified:
            return IntegrationStatus.VERIFIED
        return IntegrationStatus.NOT_IMPLEMENTED

    def mark_verified(self) -> None:
        """Promote the tool to VERIFIED after a real successful run.

        Called by the integration test only after ``_execute`` produced at least
        one Source. Raising keeps the invariant that VERIFIED always implies a
        real, tested execution.
        """
        type(self)._integration_verified = True
        self._logger.info("Research tool marked VERIFIED", extra={"tool": self.name})

    def capability_matrix(self) -> dict[str, dict[str, str]]:
        """Return the granular per-dimension status matrix (Addendum §4)."""
        matrix: dict[str, dict[str, str]] = {}
        for dimension, status in self.capabilities.items():
            matrix[dimension] = {
                "status": status,
                "evidence": self._evidence.get(dimension, ""),
            }
        return matrix

    def _mark_capability(self, dimension: str, *, evidence: str) -> None:
        """Mark a single dimension VERIFIED with its evidence (Addendum §4)."""
        self.capabilities[dimension] = "VERIFIED"
        self._evidence[dimension] = evidence

    # -------------------------------------------------------------- execution
    def _execute(self, request: ResearchRequest) -> ResearchResponse:
        """Run the search, normalize results, and enforce the local limit."""
        # Exceptions propagate to BaseTool.execute(), which converts them into a
        # structured failure response (Addendum §8: never an empty success).
        sources, raw_count, request_url, raw_text = self._search(request)

        returned_count = len(sources)
        local_truncation = returned_count > request.max_results
        if local_truncation:
            self._logger.warning(
                "Provider returned more records than requested; truncating locally",
                extra={
                    "tool": self.name,
                    "returned": returned_count,
                    "requested_max": request.max_results,
                },
            )
            sources = sources[: request.max_results]

        self._logger.info(
            "Research search completed",
            extra={
                "tool": self.name,
                "raw": raw_count,
                "returned": returned_count,
                "results": len(sources),
            },
        )

        return ResearchResponse(
            success=True,
            results=sources,
            result_count=len(sources),
            raw_count=raw_count,
            requested_max=request.max_results,
            returned_count=returned_count,
            local_truncation=local_truncation,
            query_used=request.query,
            request_url=request_url,
            raw_response_text=raw_text,
            status=self.status(),
        )

    # ------------------------------------------------------------------ hook
    def _search(
        self, request: ResearchRequest
    ) -> tuple[list[Source], int, str, str]:
        """Provider implementation.

        Returns
        -------
        (sources, raw_count, request_url, raw_text)
            Normalized sources, the raw record count, the final request URL, and
            the preserved (truncated) raw response body.
        """
        raise NotImplementedError
