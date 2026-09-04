"""PubMed research tool (E-utilities, no API key).

Specification anchors:
  * ARCHITECTURE.md §5 — PubMed is a citation/data source.
  * PHASE 3 EXECUTION ADDENDUM §3 — endpoints and field names are verified
    against real runtime responses, not assumed from a plan.

VERIFIED BEHAVIOUR (real HTTP responses, 2026-09-03):
  * ``GET eutils/esearch.fcgi?db=pubmed&term=...&retmax=N&retmode=json`` →
    ``{"esearchresult": {"count": "...", "idlist": ["42683927", ...]}}``.
  * ``GET eutils/esummary.fcgi?db=pubmed&id=ID1,ID2&retmode=json`` →
    ``{"result": {"uids": [...], "<uid>": {...}}}`` where each record carries
    ``title``, ``authors`` (list of ``{name}``), ``source`` (journal abbrev),
    ``fulljournalname``, ``pubdate``, ``volume``, ``issue``, ``pages``,
    ``articleids`` (list of ``{idtype, value}``, incl. ``doi``), ``pubtype``,
    ``issn``, ``essn``.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from src.core.config import get_config
from src.schemas.source import Source
from src.tools.http_client import HttpClient
from src.tools.research_tool import ResearchRequest, ResearchTool
from src.tools.source_mapper import source_from_dict

__all__ = ["PubMedTool"]


class PubMedTool(ResearchTool):
    """PubMed/NCBI E-utilities bibliographic search (esearch + esummary)."""

    origin: ClassVar[str] = "pubmed"
    tool_name: ClassVar[str] = "pubmed"

    capabilities: ClassVar[dict[str, str]] = {
        "query_field_title": "NOT_VERIFIED",
        "query_field_years": "NOT_VERIFIED",
        "query_field_max": "NOT_VERIFIED",
    }

    _ESEARCH_URL: ClassVar[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    _ESUMMARY_URL: ClassVar[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def _client(self) -> HttpClient:
        cfg = get_config().tool("pubmed")
        return HttpClient(
            tool_name=self.name,
            contact_email=cfg.contact_email,
            timeout_seconds=cfg.timeout_seconds,
            max_retries=get_config().research.max_discovery_retries,
        )

    def _build_term(self, request: ResearchRequest) -> str:
        term = request.query
        if request.year_start is not None or request.year_end is not None:
            start = request.year_start or 1800
            end = request.year_end or 2100
            # PubMed supports a date range filter by publication date.
            term = f"{term} AND ({start}:{end}[dp])"
        return term

    def _search(
        self, request: ResearchRequest
    ) -> tuple[list[Source], int, str, str]:
        client = self._client()
        term = self._build_term(request)

        # Step 1: esearch → PMID list.
        esearch_params = {
            "db": "pubmed",
            "term": term,
            "retmax": request.max_results,
            "retmode": "json",
        }
        esearch = client.get_json(self._ESEARCH_URL, params=esearch_params)
        esearch_payload = esearch.json()
        idlist = (esearch_payload.get("esearchresult") or {}).get("idlist") or []

        if not idlist:
            # A search with zero matches is a legitimate, empty success.
            return [], 0, esearch.url, esearch.text[:4000]

        # NCBI politeness: no more than 3 requests/second.
        time.sleep(0.4)

        # Step 2: esummary → full records.
        esummary_params = {
            "db": "pubmed",
            "id": ",".join(str(pid) for pid in idlist),
            "retmode": "json",
        }
        esummary = client.get_json(self._ESUMMARY_URL, params=esummary_params)
        summary_payload = esummary.json()
        result_map = summary_payload.get("result") or {}
        uids = result_map.get("uids") or []

        sources: list[Source] = []
        for uid in uids:
            record = result_map.get(uid)
            if isinstance(record, dict):
                source = self._record_to_source(uid, record)
                if source.title:
                    sources.append(source)

        return sources, len(uids), esummary.url, esummary.text[:4000]

    def _record_to_source(self, uid: str, record: dict[str, Any]) -> Source:
        authors = [a["name"] for a in record.get("authors") or [] if isinstance(a, dict) and a.get("name")]

        doi = None
        for article_id in record.get("articleids") or []:
            if isinstance(article_id, dict) and article_id.get("idtype") == "doi":
                doi = article_id.get("value")
                break

        mapped = {
            "title": record.get("title"),
            "authors": authors,
            "year": self._year_from_pubdate(record.get("pubdate")),
            "venue": record.get("fulljournalname") or record.get("source"),
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            "abstract": None,
            "source_type": self._type_from_pubtype(record.get("pubtype")),
            "citation_count": None,
        }
        return source_from_dict({**record, **mapped}, origin=self.origin)

    @staticmethod
    def _year_from_pubdate(pubdate: Any) -> int | None:
        if not isinstance(pubdate, str):
            return None
        # Formats observed: "2026 Sep 1", "2015", "2015 Jan-Feb".
        for token in pubdate.split():
            if token.isdigit() and len(token) == 4:
                return int(token)
        return None

    @staticmethod
    def _type_from_pubtype(pubtype: Any) -> str | None:
        if not pubtype:
            return None
        if isinstance(pubtype, list):
            pubtype = pubtype[0] if pubtype else None
        if not isinstance(pubtype, str):
            return None
        lowered = pubtype.lower()
        if "journal" in lowered:
            return "journal-article"
        if "review" in lowered:
            return "journal-article"
        return None
