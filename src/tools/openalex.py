"""OpenAlex research tool (HTTP, no API key).

Specification anchors:
  * ARCHITECTURE.md §5 — OpenAlex is a citation/data source.
  * PHASE 3 EXECUTION ADDENDUM §3 — endpoints and field names are verified
    against real runtime responses, not assumed from a plan.

VERIFIED BEHAVIOUR (real HTTP response, 2026-09-03):
  * ``GET /works?search=...&per-page=N`` returns ``{"results": [...]}``.
  * Each work carries: ``title``, ``display_name``, ``publication_year``,
    ``publication_date``, ``doi`` (full URL), ``authorships`` (list of
    ``{author: {display_name}}``), ``primary_location.source.display_name``
    (venue), ``cited_by_count``, ``type`` (e.g. ``"article"``),
    ``primary_location.landing_page_url``, ``ids``, ``abstract_inverted_index``.
  * ``abstract_inverted_index`` is an inverted word index, not plain text; it is
    preserved verbatim in ``Source.metadata`` rather than reconstructed.
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import Source
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import source_from_dict

__all__ = ["OpenAlexTool"]


class OpenAlexTool(ResearchTool):
    """OpenAlex bibliographic search via the public REST API."""

    origin: ClassVar[str] = "openalex"
    tool_name: ClassVar[str] = "openalex"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _BASE_URL: ClassVar[str] = "https://api.openalex.org/works"

    def _client(self) -> HttpClient:
        cfg = get_config().tool("openalex")
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=cfg.timeout_seconds,
            max_retries=get_config().research.max_discovery_retries,
        )

    def _build_params(self, request: ResearchRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "search": request.query,
            "per-page": request.max_results,
        }
        filters: list[str] = []
        if request.year_start is not None:
            filters.append(f"from_publication_year:{request.year_start}")
        if request.year_end is not None:
            filters.append(f"to_publication_year:{request.year_end}")
        if filters:
            params["filter"] = ",".join(filters)
        return params

    def _item_to_source(self, item: dict[str, Any]) -> Source:
        authors: list[str] = []
        for authorship in item.get("authorships") or []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author") or {}
            name = author.get("display_name")
            if isinstance(name, str) and name.strip():
                authors.append(name.strip())

        venue = None
        primary = item.get("primary_location") or {}
        source_info = primary.get("source") or {}
        if isinstance(source_info, dict):
            venue = source_info.get("display_name")

        url = None
        if isinstance(primary, dict):
            url = primary.get("landing_page_url")

        # ``doi`` is a full URL (e.g. https://doi.org/10.x/...); normalize_doi
        # strips it inside source_from_dict.
        mapped = {
            "title": item.get("title"),
            "authors": authors,
            "year": item.get("publication_year"),
            "venue": venue,
            "doi": item.get("doi"),
            "url": url,
            "abstract": None,
            "source_type": item.get("type"),
            "citation_count": item.get("cited_by_count"),
        }
        return source_from_dict({**item, **mapped}, origin=self.origin)

    def _search(
        self, request: ResearchRequest
    ) -> tuple[list[Source], int, str, str]:
        client = self._client()
        params = self._build_params(request)
        result = client.get_json(self._BASE_URL, params=params)
        payload = result.json()

        items = payload.get("results") or []
        sources = [self._item_to_source(item) for item in items if isinstance(item, dict)]
        sources = [s for s in sources if s.title]

        return sources, len(items), result.url, result.text[:4000]
