"""DOAB (Directory of Open Access Books) research tool.

Specification anchors:
  * AGENT_CONSTITUTION.md §1-5: source integrity, never fabricate bibliographic data.
  * SYSTEM_RULES.md §H.47-50: honest integration status, preserve raw records.
  * Bagian B: Open-access academic books discovery via official REST API.
  * Bagian C: Access and rights status classification.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import AccessMode, RightsStatus, Source, SourceType
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import coerce_year, normalize_doi, source_from_dict

__all__ = ["DOABTool"]

_URL_PATTERN = re.compile(r"https?://[^\s\"')]+", re.I)


class DOABTool(ResearchTool):
    """DOAB bibliographic search via Directory of Open Access Books REST API."""

    origin: ClassVar[str] = "doab"
    tool_name: ClassVar[str] = "doab"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_keywords": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _integration_verified: ClassVar[bool] = False

    _BASE_URL: ClassVar[str] = "https://directory.doabooks.org/rest/search"
    _HOST: ClassVar[str] = "https://directory.doabooks.org"

    def _client(self) -> HttpClient:
        cfg = get_config().tool("doab")
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=self._timeout(),
            max_retries=get_config().research.max_discovery_retries,
        )

    def _timeout(self) -> int:
        return get_config().tool("doab").timeout_seconds

    def _build_params(self, request: ResearchRequest) -> dict[str, Any]:
        return {
            "query": request.query,
            "limit": request.max_results,
            "expand": "metadata,bitstreams",
        }

    def _item_to_source(self, item: dict[str, Any]) -> Source:
        metadata_list = item.get("metadata") or []
        meta_by_key: dict[str, list[str]] = {}
        if isinstance(metadata_list, list):
            for entry in metadata_list:
                if isinstance(entry, dict) and entry.get("key") and entry.get("value") is not None:
                    meta_by_key.setdefault(entry["key"], []).append(str(entry["value"]).strip())

        title = (meta_by_key.get("dc.title") or [""])[0]
        authors = meta_by_key.get("dc.contributor.author") or []

        issued_raw = (meta_by_key.get("dc.date.issued") or meta_by_key.get("dc.date.available") or [None])[0]
        year = coerce_year(issued_raw)

        publisher = (
            meta_by_key.get("publisher.name")
            or meta_by_key.get("oapen.relation.isPublishedBy")
            or meta_by_key.get("oapen.imprint")
            or [None]
        )[0]

        raw_doi = (meta_by_key.get("oapen.identifier.doi") or meta_by_key.get("dc.identifier.doi") or [None])[0]
        doi = normalize_doi(raw_doi)

        # ISBN detection
        isbn = None
        for key in ("dc.identifier.isbn", "oapen.identifier.isbn"):
            if meta_by_key.get(key):
                isbn = meta_by_key[key][0]
                break
        if not isbn:
            for ident in meta_by_key.get("dc.identifier") or []:
                clean_id = re.sub(r"[^0-9X]", "", ident.upper())
                if len(clean_id) in {10, 13} and (clean_id.startswith("978") or clean_id.startswith("979") or len(clean_id) == 10):
                    isbn = ident
                    break

        language = (meta_by_key.get("dc.language") or meta_by_key.get("dc.language.iso") or [None])[0]

        subjects: list[str] = []
        for key in ("dc.subject.classification", "dc.subject", "dc.subject.other"):
            subjects.extend(meta_by_key.get(key) or [])

        landing_url = (meta_by_key.get("dc.identifier.uri") or [None])[0]
        if not landing_url and item.get("handle"):
            landing_url = f"{self._HOST}/handle/{item['handle']}"

        abstract = (meta_by_key.get("dc.description.abstract") or [None])[0]

        license_text = (meta_by_key.get("publisher.oalicense") or meta_by_key.get("dc.rights") or [None])[0]
        license_url = (meta_by_key.get("dc.rights.uri") or [None])[0]
        if not license_url and license_text:
            match = _URL_PATTERN.search(license_text)
            if match:
                license_url = match.group(0)

        # Bitstreams / Download URLs
        download_urls: list[str] = []
        bitstreams = item.get("bitstreams") or []
        for bs in bitstreams:
            if not isinstance(bs, dict):
                continue
            mime = (bs.get("mimeType") or "").lower()
            name = (bs.get("name") or "").lower()
            bundle = (bs.get("bundleName") or "").upper()
            rel_link = bs.get("retrieveLink")
            if not rel_link:
                continue

            # Prioritize original or PDF documents; avoid standalone metadata exports / thumbnails
            is_pdf = "pdf" in mime or name.endswith(".pdf")
            is_original = bundle in {"ORIGINAL", "CONTENT"}
            if (is_pdf or is_original) and bundle not in {"THUMBNAIL", "EXPORT"}:
                full_dl = rel_link if rel_link.startswith("http") else f"{self._HOST}{rel_link}"
                if full_dl not in download_urls:
                    download_urls.append(full_dl)

        record_id = item.get("uuid") or item.get("handle") or ""

        mapped = {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": publisher,
            "publisher": publisher,
            "doi": doi,
            "isbn": isbn,
            "language": language,
            "landing_url": landing_url,
            "url": landing_url,
            "abstract": abstract,
            "download_urls": download_urls,
            "license": license_text,
            "license_url": license_url,
            "provider": self.origin,
            "provider_record_id": str(record_id),
            "source_type": SourceType.BOOK,
            "subject": subjects,
            "handle": item.get("handle"),
        }
        return source_from_dict(mapped, origin=self.origin, source_type_hint=SourceType.BOOK)

    def _search(self, request: ResearchRequest) -> tuple[list[Source], int, str, str]:
        client = self._client()
        params = self._build_params(request)
        result = client.get_json(self._endpoint(self._BASE_URL), params=params)
        payload = result.json()

        items = payload if isinstance(payload, list) else (payload.get("items") or [])
        sources = [self._item_to_source(item) for item in items if isinstance(item, dict)]
        sources = [s for s in sources if s.title]

        # Filter by year range if requested
        if request.year_start is not None:
            sources = [s for s in sources if s.year is None or s.year >= request.year_start]
        if request.year_end is not None:
            sources = [s for s in sources if s.year is None or s.year <= request.year_end]

        return sources, len(items), result.url, result.text[:4000]
