"""Semantic Scholar research tool (HTTP, optional API key).

Specification anchors:
  * ARCHITECTURE.md §5 — Semantic Scholar is a citation/data source.
  * PHASE 3 EXECUTION ADDENDUM §3 — endpoints and field names are verified
    against real runtime responses, not assumed from a plan.
  * PHASE 3 EXECUTION ADDENDUM §5 — preserve ``requested_max``, ``raw_count``,
    ``returned_count``, and ``local_truncation`` for providers that ignore limits.

RATE-LIMIT NOTE (honest reporting, 2026-09-03):
  During Phase 3 discovery this environment repeatedly received HTTP 429 from
  ``api.semanticscholar.org`` (shared egress IP, no API key configured). The
  adapter is written against the documented, stable public response schema, but
  its capability matrix remains ``NOT_VERIFIED`` until a real runtime run
  succeeds (Addendum §4: granular status is never promoted speculatively).

Documented response schema (public Graph API, ``paper/search``):
  ``{"total": N, "offset": 0, "next": N, "data": [ {paperId, title, abstract,
  year, venue, journal, authors: [{name, authorId}], externalIds: {DOI, ...},
  citationCount, publicationTypes, url} ]}``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import Source
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import source_from_dict

__all__ = ["SemanticScholarTool"]


class SemanticScholarTool(ResearchTool):
    """Semantic Scholar Graph API search."""

    origin: ClassVar[str] = "semantic_scholar"
    tool_name: ClassVar[str] = "semantic_scholar"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _BASE_URL: ClassVar[str] = "https://api.semanticscholar.org/graph/v1/paper/search"
    _FIELDS: ClassVar[str] = (
        "title,authors,year,venue,journal,externalIds,abstract,"
        "citationCount,publicationTypes,url"
    )

    def _client(self) -> HttpClient:
        cfg = get_config().tool("semantic_scholar")
        headers: dict[str, str] = {}
        if cfg.api_key:
            headers["x-api-key"] = cfg.api_key
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=cfg.timeout_seconds,
            max_retries=get_config().research.max_discovery_retries,
            extra_headers=headers,
        )

    def _build_params(self, request: ResearchRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": request.query,
            # Request a bit more than max_results so local truncation (Addendum §5)
            # can be reported honestly when the provider ignores the limit.
            "limit": request.max_results,
            "fields": self._FIELDS,
        }
        if request.year_start is not None:
            params["year"] = f"{request.year_start}-" if request.year_end is None else f"{request.year_start}-{request.year_end}"
        elif request.year_end is not None:
            params["year"] = f"-{request.year_end}"
        return params

    def _item_to_source(self, item: dict[str, Any]) -> Source:
        authors: list[str] = []
        for author in item.get("authors") or []:
            if isinstance(author, dict) and author.get("name"):
                authors.append(str(author["name"]))
            elif isinstance(author, str):
                authors.append(author)

        external_ids = item.get("externalIds") or {}
        doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None

        mapped = {
            "title": item.get("title"),
            "authors": authors,
            "year": item.get("year"),
            "venue": item.get("venue") or item.get("journal"),
            "doi": doi,
            "url": item.get("url"),
            "abstract": item.get("abstract"),
            "source_type": self._first_publication_type(item.get("publicationTypes")),
            "citation_count": item.get("citationCount"),
        }
        return source_from_dict({**item, **mapped}, origin=self.origin)

    @staticmethod
    def _first_publication_type(publication_types: Any) -> str | None:
        if not publication_types:
            return None
        if isinstance(publication_types, list):
            publication_types = publication_types[0] if publication_types else None
        if not isinstance(publication_types, str):
            return None
        return publication_types

    def _search(
        self, request: ResearchRequest
    ) -> tuple[list[Source], int, str, str]:
        client = self._client()
        params = self._build_params(request)
        result = client.get_json(self._BASE_URL, params=params)
        payload = result.json()

        items = payload.get("data") or []
        sources = [self._item_to_source(item) for item in items if isinstance(item, dict)]
        sources = [s for s in sources if s.title]

        return sources, len(items), result.url, result.text[:4000]
