"""Crossref research tool (HTTP, no API key).

Specification anchors:
  * ARCHITECTURE.md §5 — Crossref retrieves citations based on queries.
  * PHASE 3 EXECUTION ADDENDUM §3 — endpoints and field names are verified
    against real runtime responses, not assumed from a plan.

VERIFIED BEHAVIOUR (real HTTP response, 2026-09-03):
  * ``GET /works?query.bibliographic=...&rows=N`` returns
    ``{"message": {"items": [...]}}``.
  * Each item carries: ``title`` (list of strings), ``author`` (list of
    ``{given, family}``), ``issued`` (``date-parts``), ``container-title``
    (list), ``DOI``, ``URL``, ``type``, ``is-referenced-by-count``, ``publisher``,
    ``abstract`` (optional), ``volume``, ``issue``, ``page``.
  * A polite ``User-Agent`` + ``From`` header is required; without it the API
    returns HTTP 429 (rate-limited).
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import Source
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import source_from_dict

__all__ = ["CrossrefTool"]


class CrossrefTool(ResearchTool):
    """Crossref bibliographic search via the public REST API."""

    origin: ClassVar[str] = "crossref"
    tool_name: ClassVar[str] = "crossref"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _BASE_URL: ClassVar[str] = "https://api.crossref.org/works"

    def _client(self) -> HttpClient:
        cfg = get_config().tool("crossref")
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=self._timeout(),
            max_retries=get_config().research.max_discovery_retries,
        )

    def _timeout(self) -> int:
        return get_config().tool("crossref").timeout_seconds

    def _build_params(self, request: ResearchRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query.bibliographic": request.query,
            "rows": request.max_results,
        }
        # Crossref year filter: open-ended via filter=from-pub-date,until-pub-date.
        if request.year_start is not None:
            params["filter"] = f"from-pub-date:{request.year_start}-01-01"
        if request.year_end is not None:
            existing = params.get("filter", "")
            suffix = f"until-pub-date:{request.year_end}-12-31"
            params["filter"] = f"{existing},{suffix}" if existing else suffix
        return params

    def _item_to_source(self, item: dict[str, Any]) -> Source:
        # Crossref titles/authors/container-title are lists.
        title = ""
        titles = item.get("title") or []
        if titles and isinstance(titles[0], str):
            title = titles[0]

        authors: list[str] = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            given = author.get("given") or ""
            family = author.get("family") or ""
            name = " ".join(part for part in (given, family) if part).strip()
            if name:
                authors.append(name)

        container = item.get("container-title") or []
        venue = container[0] if container and isinstance(container[0], str) else None

        year = None
        issued = item.get("issued") or {}
        date_parts = issued.get("date-parts") or []
        if date_parts and date_parts[0]:
            year = date_parts[0][0]

        mapped = {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "doi": item.get("DOI"),
            "url": item.get("URL"),
            "abstract": item.get("abstract"),
            "source_type": item.get("type"),
            "citation_count": item.get("is-referenced-by-count"),
        }
        return source_from_dict({**item, **mapped}, origin=self.origin)

    def _search(
        self, request: ResearchRequest
    ) -> tuple[list[Source], int, str, str]:
        client = self._client()
        params = self._build_params(request)
        result = client.get_json(self._BASE_URL, params=params)
        payload = result.json()

        items = (payload.get("message") or {}).get("items") or []
        sources = [self._item_to_source(item) for item in items if isinstance(item, dict)]
        # Drop records with no title at all (minimal validity, never fabricated).
        sources = [s for s in sources if s.title]

        return sources, len(items), result.url, result.text[:4000]
