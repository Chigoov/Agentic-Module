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

import urllib.parse
from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import Source
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import best_title_match, normalize_doi, source_from_dict

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

    # --------------------------------------------------------------- lookups
    def lookup_by_doi(self, doi: str) -> Source | None:
        """Resolve a single work by DOI, returning a ``Source`` or ``None``.

        Uses the canonical ``GET /works/{doi}`` endpoint. Returns ``None`` for a
        missing or malformed DOI, or when the provider returns no titled record
        (never fabricates a source).
        """
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        client = self._client()
        url = f"{self._BASE_URL}/{urllib.parse.quote(normalized, safe='')}"
        result = client.get_json(url)
        item = result.json().get("message") or {}
        if not isinstance(item, dict):
            return None
        source = self._item_to_source(item)
        return source if source.title else None

    def lookup_by_bibliographic(
        self,
        *,
        title: str,
        authors: list[str] | None = None,
        year: int | None = None,
    ) -> Source | None:
        """Find the single best bibliographic match for a candidate record.

        Searches by title (with an optional exact-year filter when ``year`` is
        supplied) and returns the record whose normalized title best matches the
        query title, or ``None`` when the search returns nothing usable.
        """
        request = ResearchRequest(
            query=title,
            year_start=year,
            year_end=year,
            max_results=10,
        )
        response = self._execute(request)
        if not response.success or not response.results:
            return None
        best_title, _score = best_title_match(title, [s.title for s in response.results])
        for source in response.results:
            if source.title == best_title:
                return source
        return response.results[0]
