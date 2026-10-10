"""Open Library research tool for book availability and metadata.

Specification anchors:
  * AGENT_CONSTITUTION.md §1-5: source integrity, never fabricate bibliographic data.
  * SYSTEM_RULES.md §H.47-50: honest integration status, preserve raw records.
  * Bagian B: Open Library as secondary book metadata and availability provider.
  * Bagian C: Access and rights status classification (borrowable != open download).
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import AccessMode, RightsStatus, Source, SourceType
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import coerce_year, source_from_dict

__all__ = ["OpenLibraryTool"]


class OpenLibraryTool(ResearchTool):
    """Open Library bibliographic search via the official search.json API."""

    origin: ClassVar[str] = "open_library"
    tool_name: ClassVar[str] = "open_library"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_keywords": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _integration_verified: ClassVar[bool] = False

    _BASE_URL: ClassVar[str] = "https://openlibrary.org/search.json"
    _HOST: ClassVar[str] = "https://openlibrary.org"

    def _client(self) -> HttpClient:
        cfg = get_config().tool("open_library")
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=self._timeout(),
            max_retries=get_config().research.max_discovery_retries,
        )

    def _timeout(self) -> int:
        return get_config().tool("open_library").timeout_seconds

    def _build_params(self, request: ResearchRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "q": request.query,
            "limit": request.max_results,
        }
        return params

    def _item_to_source(self, doc: dict[str, Any]) -> Source:
        title = str(doc.get("title") or "").strip()
        authors = [str(a).strip() for a in doc.get("author_name") or [] if str(a).strip()]

        year = None
        if doc.get("first_publish_year"):
            year = coerce_year(doc["first_publish_year"])
        elif doc.get("publish_year"):
            years = [coerce_year(y) for y in doc["publish_year"] if coerce_year(y) is not None]
            if years:
                year = min(years)

        publishers = doc.get("publisher") or []
        publisher = str(publishers[0]).strip() if publishers else None

        isbns = doc.get("isbn") or []
        isbn = str(isbns[0]).strip() if isbns else None

        languages = doc.get("language") or []
        language = str(languages[0]).strip() if languages else None

        key = doc.get("key") or ""
        landing_url = f"{self._HOST}{key}" if key.startswith("/") else None

        subjects = doc.get("subject") or []

        # Access & Rights evaluation
        ebook_access = str(doc.get("ebook_access") or "").lower()
        ia_list = doc.get("ia") or []
        download_urls: list[str] = []
        rights_status = RightsStatus.UNKNOWN
        access_mode = AccessMode.UNKNOWN

        if ebook_access == "public" and ia_list:
            # Public access is not a license or a verified PDF filename.
            access_mode = AccessMode.READ_ONLINE
        elif ebook_access in {"borrowable", "borrow", "inlibrary"}:
            access_mode = AccessMode.BORROW_ONLY
            rights_status = RightsStatus.RESTRICTED
        elif ebook_access in {"printdisabled"}:
            access_mode = AccessMode.UNKNOWN
            rights_status = RightsStatus.RESTRICTED
        elif ebook_access in {"preview", "preview_only"}:
            access_mode = AccessMode.PREVIEW_ONLY
            rights_status = RightsStatus.UNKNOWN

        mapped = {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": publisher,
            "publisher": publisher,
            "isbn": isbn,
            "language": language,
            "landing_url": landing_url,
            "url": landing_url,
            "download_urls": download_urls,
            "rights_status": rights_status,
            "access_mode": access_mode,
            "provider": self.origin,
            "provider_record_id": key,
            "source_type": SourceType.BOOK,
            "subject": subjects,
            "ebook_access": ebook_access,
            "ia": ia_list,
        }
        return source_from_dict(mapped, origin=self.origin, source_type_hint=SourceType.BOOK)

    def _search(self, request: ResearchRequest) -> tuple[list[Source], int, str, str]:
        client = self._client()
        params = self._build_params(request)
        result = client.get_json(self._endpoint(self._BASE_URL), params=params)
        payload = result.json()

        docs = payload.get("docs") or []
        sources = [self._item_to_source(doc) for doc in docs if isinstance(doc, dict)]
        sources = [s for s in sources if s.title]

        if request.year_start is not None:
            sources = [s for s in sources if s.year is None or s.year >= request.year_start]
        if request.year_end is not None:
            sources = [s for s in sources if s.year is None or s.year <= request.year_end]

        return sources, len(docs), result.url, result.text[:4000]
