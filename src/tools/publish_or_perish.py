"""Publish or Perish CLI adapter (Phase 2 — real integration).

Specification anchors:
  * ARCHITECTURE.md §5 — "Publish or Perish: retrieves citations based on
    author/title/keyword queries."
  * SYSTEM_RULES.md §H.47–§H.49 — never claim an integration works until tested.
  * 00_MASTER_INSTRUCTION.md §9/§10 — source discovery and validation level C.

CLI DISCOVERY (performed against the real install on 2026-09-02, NOT assumed):

  Executable:    ``C:/Program Files/Harzing's Publish or Perish 8/pop8query.exe``
                 The CLI tool is ``pop8query.exe``; ``pop8.exe`` is the GUI app.

  ``pop8query --help`` revealed:

    Search:  pop8query options [--datasource] [outfile]
    Data source options: --crossref, --gscholar, --openalex, --pubmed,
                 --semscholar, --scopus, --wos, --lens, etc.
    Query fields: --author, --affiliation, --citedid, --field, --issn,
                 --journal, --title, --keywords, --years (also year, from-, -to)
                 or --raw <native_syntax>
    Executive: -f argfile, --direct, --dryrun, --noerrlog, --offline,
                 --syntax, --datadir, --max <number>, --maxage <hours>, --wait
    Output: --format <fmt>  (csv, json, jsonl, ris, bibtex, xml, md, etc.)
                 --sort [-]<field> (author, cites, year, title, source, ...)
                 [outfile] — write to file (extension selects format), else stdout.

  VERIFIED BEHAVIOUR (real executions on 2026-09-02):
    * ``--crossref --title "deep learning education" --format jsonl --max 3 out.jsonl``
        → EXIT 0, produced JSONL, one object per line with real records:
          fields present: type, title, source, publisher, doi, article_url,
          fulltext_url, abstract, rank, year, volume, issue, startpage, endpage,
          cites, ecc, use, authors[].  Crossref works WITHOUT any API key.
    * ``--crossref --title "x" --format jsonl --max 3 --syntax``
        → prints native query (query.bibliographic=...) without contacting server.
    * ``--gscholar --dryrun`` → Google Scholar cancels on dry-run (exit 3), so
        Google Scholar is NOT used for real automated queries here. Crossref is
        the reliable default.

  DATA SOURCE SELECTION: ``source`` maps to a ``--datasource`` flag:
      google_scholar -> --gscholar   (note: dry-run cancels; untested live)
      crossref       -> --crossref   (VERIFIED WORKING, no API key)
      openalex       -> --openalex
      pubmed         -> --pubmed
      semantic_scholar -> --semscholar

IMPORTANT CAVEAT (honest reporting):
  This adapter is written against the *discovered* Crossref behaviour, which was
  exercised for real and produced valid output. The status() method returns
  VERIFIED only after a real search in THIS environment succeeded AND parsed into
  at least one Source record. Status remains NOT_IMPLEMENTED otherwise.

PHASE 2.1 HARDENING (2026-09-02) — granular capability status:
  A single tool-level ``VERIFIED`` never implies every PoP capability is proven.
  ``capability_matrix()`` reports per-dimension status (tool / CLI / datasource /
  query field / output / normalization) recorded from real runtime probes. See
  docs/POP_CAPABILITY_MATRIX.md for the full evidence table.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field

from src.core.config import get_config
from src.core.errors import IntegrationError
from src.core.status import IntegrationStatus
from src.core.logging import get_logger
from src.schemas.source import Source
from src.tools.base import BaseTool, ToolRequest, ToolResponse
from src.tools.source_mapper import source_from_dict

__all__ = [
    "PublishOrPerishRequest",
    "PublishOrPerishResponse",
    "PublishOrPerishTool",
    "POP_SOURCES",
]

_logger = get_logger(__name__)

#: Module-level probe flag. Set ONLY by a real, successful, end-to-end run of
#: the CLI that produced at least one normalized Source record. Reading it lets
#: status() report VERIFIED after the integration test proves the integration,
#: and lets it stay conservative (NOT_IMPLEMENTED) before that.
_integration_verified: bool = False

#: Data source keyword -> the actual PoP ``--datasource`` flag (from --help).
POP_SOURCES: dict[str, str] = {
    "google_scholar": "--gscholar",
    "crossref": "--crossref",
    "openalex": "--openalex",
    "pubmed": "--pubmed",
    "semantic_scholar": "--semscholar",
}

#: Query field keyword -> the actual PoP query field flag (from --help).
#: Defined once at module level so the mapping and the "unknown field" error
#: message can never drift apart (fixes a latent Phase 2 bug where the error
#: path referenced a duplicate global ``field_flag_map``).
_QUERY_FIELD_FLAGS: dict[str, str] = {
    "title": "--title",
    "keywords": "--keywords",
    "author": "--author",
    "journal": "--journal",
    "affiliation": "--affiliation",
    "issn": "--issn",
    "field": "--field",
}

#: Granular per-dimension capability matrix, recorded from REAL runtime probes
#: on 2026-09-02 (Phase 2.1 hardening). A single tool-level ``VERIFIED`` never
#: implies every capability is proven; each dimension is reported separately.
#: Statuses (per Phase 2.1 directive): VERIFIED, PARTIALLY_VERIFIED,
#: PENDING_CONFIGURATION, UNAVAILABLE, FAILED.
_CAPABILITY_MATRIX: dict[str, dict[str, str]] = {
    "tool_availability": {
        "status": "VERIFIED",
        "evidence": "pop8query.exe resolved from config and confirmed on disk",
    },
    "cli_availability": {
        "status": "VERIFIED",
        "evidence": "--help executed (exit 0) revealing the full flag set",
    },
    "output_availability": {
        "status": "VERIFIED",
        "evidence": "--format jsonl writes one JSON object per line; decoded utf-8-sig",
    },
    "normalization_availability": {
        "status": "VERIFIED",
        "evidence": "title/authors/year/venue/doi/url mapped; dict authors flattened to names",
    },
    "datasource_crossref": {
        "status": "VERIFIED",
        "evidence": "title/keywords/author/journal/sort exit 0 with real records; no API key",
    },
    "datasource_openalex": {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "single-term title works; multi-term title & keywords fail (exit 2, source limits)",
    },
    "datasource_pubmed": {
        "status": "VERIFIED",
        "evidence": "title search exit 0 with 3 real records",
    },
    "datasource_semantic_scholar": {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "keywords works but --max is ignored (returned 1000); --title unsupported",
    },
    "datasource_google_scholar": {
        "status": "UNAVAILABLE",
        "evidence": "--dryrun cancels (exit 3); live automation not relied upon",
    },
    "datasource_scopus": {
        "status": "PENDING_CONFIGURATION",
        "evidence": "requires credentials; not tested",
    },
    "datasource_wos": {
        "status": "PENDING_CONFIGURATION",
        "evidence": "requires credentials; not tested",
    },
    "datasource_lens": {
        "status": "PENDING_CONFIGURATION",
        "evidence": "requires credentials; not tested",
    },
    "query_field_title": {
        "status": "VERIFIED",
        "evidence": "crossref/pubmed/openalex(single-term) exit 0",
    },
    "query_field_keywords": {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "crossref & semantic_scholar exit 0; openalex fails",
    },
    "query_field_author": {
        "status": "VERIFIED",
        "evidence": "crossref full-name author exit 0 and matched the author",
    },
    "query_field_journal": {
        "status": "VERIFIED",
        "evidence": "crossref journal exit 0",
    },
    "query_field_years": {
        "status": "VERIFIED",
        "evidence": "--years from-to passes through to the command line",
    },
    "query_field_max": {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "crossref respects --max; semantic_scholar ignores it (adapter truncates)",
    },
    "query_field_sort": {
        "status": "VERIFIED",
        "evidence": "year and -cites exit 0 on crossref",
    },
}



class PublishOrPerishRequest(ToolRequest):
    """Input contract for a Publish or Perish search.

    Attributes
    ----------
    query:
        Search query text (title/keyword/author, depending on ``query_field``).
    query_field:
        Which PoP query field to populate: title, keywords, author, journal,
        affiliation, issn, field. Maps to the corresponding ``--field`` option.
    source:
        Data source key (``crossref``, ``google_scholar``, ... ). Crossref is
        the verified default because it needs no API key.
    max_results:
        Maximum number of results (``--max``). PoP caps per source.
    year_start / year_end:
        Optional publication-year filter (``--years from-to``). When both are
        ``None`` no year filter is applied.
    sort:
        Optional sort field (author, cites, year, title, source).
    timeout_seconds:
        Subprocess timeout. Defaults to the configured ``timeout_seconds``.
    """

    query: str = Field(min_length=1)
    query_field: str = "title"
    source: str = "crossref"
    max_results: int = Field(default=50, ge=1, le=1000)
    year_start: int | None = None
    year_end: int | None = None
    sort: str | None = None
    timeout_seconds: int | None = None


class PublishOrPerishResponse(ToolResponse):
    """Output contract for a Publish or Perish search.

    Attributes
    ----------
    results:
        Normalized ``Source``-shaped records. Each has at least ``title`` and
        ``authors``; unknown fields remain ``None`` (never invented).
    result_count:
        Number of normalized results.
    raw_count:
        Number of raw records parsed from PoP output (may exceed result_count
        if some records could not be normalized).
    query_used:
        The query string actually executed.
    datasource:
        The data source flag used (e.g. ``--crossref``).
    command:
        The full command line that was executed, for audit/regression.
    exit_code:
        The subprocess exit code.
    detected_format:
        The output format detected (jsonl/csv/json/etc.).
    raw_output_text:
        Preserved raw output (truncated), for debugging (SYSTEM_RULES §H.50).
    """

    results: list[dict[str, Any]] = Field(default_factory=list)
    result_count: int = 0
    raw_count: int = 0
    query_used: str = ""
    datasource: str = ""
    command: str = ""
    exit_code: int | None = None
    detected_format: str = ""
    raw_output_text: str = ""


class PublishOrPerishTool(BaseTool[PublishOrPerishRequest, PublishOrPerishResponse]):
    """Real Publish or Perish CLI adapter (Phase 2).

    ``status()`` is conservative: it returns ``VERIFIED`` ONLY after a real
    search in this environment produced at least one normalized ``Source``
    record. Until then it returns ``NOT_IMPLEMENTED`` or ``CONFIGURED`` so the
    system never advertises an untested integration (SYSTEM_RULES §H.47-49).
    """

    response_model: ClassVar[type[ToolResponse]] = PublishOrPerishResponse
    tool_name: ClassVar[str] = "publish_or_perish"

    # ------------------------------------------------------------------ config
    def _executable(self) -> str | None:
        """Resolve the PoP CLI executable path.

        Priority:
          1. ``config.tools.publish_or_perish.executable_path`` (central config).
          2. ``config.tools.publish_or_perish.install_dir`` + ``pop8query.exe``.
          3. Probe ``config.tools.publish_or_perish.search_dirs`` (fallbacks).

        Returns ``None`` when no executable can be confirmed to exist.
        """
        cfg = get_config().tool("publish_or_perish")
        candidates: list[str | None] = []

        if cfg.executable_path:
            candidates.append(cfg.executable_path)
        if cfg.install_dir:
            candidates.append(str(Path(cfg.install_dir) / "pop8query.exe"))
        # Fallback: probe configured search dirs (no hardcoded paths in source).
        for directory in cfg.search_dirs:
            if directory:
                candidates.append(str(Path(directory) / "pop8query.exe"))

        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return str(Path(candidate).resolve())
        return None

    def status(self) -> IntegrationStatus:
        """Report integration status, never claiming more than is proven.

        Per SYSTEM_RULES §H.47-49 and the Phase 2 directive, this stays
        ``NOT_IMPLEMENTED`` until a real end-to-end run of the CLI has produced
        at least one normalized ``Source`` record in THIS environment. Only then
        does ``mark_verified()`` promote it to ``VERIFIED``.

        We deliberately do NOT return ``CONFIGURED`` just because the executable
        exists: that would let the tool be *called* without being proven.
        """
        # Honour a proven integration (set only at runtime after a real test,
        # never by hand) from this module's probe flag or config.
        if _integration_verified:
            return IntegrationStatus.VERIFIED
        cfg = get_config().tool("publish_or_perish")
        if cfg.integration_verified:
            return IntegrationStatus.VERIFIED

        # Not proven in this environment: refuse to advertise as callable.
        return IntegrationStatus.NOT_IMPLEMENTED

    def mark_verified(self) -> None:
        """Promote the integration to VERIFIED after a proven runtime run.

        Called by the integration test ONLY after a real search succeeded and
        produced at least one normalized Source record. Raising an error here
        (rather than silently setting the flag) keeps the invariant that
        VERIFIED always implies a real, tested execution.
        """
        global _integration_verified
        if self._executable() is None:
            raise IntegrationError(
                "Cannot mark VERIFIED: Publish or Perish executable not found",
                error_code="EXECUTABLE_NOT_FOUND",
                context={},
            )
        _integration_verified = True
        self._logger.info(
            "Publish or Perish marked VERIFIED after real execution",
            extra={"tool": self.name},
        )

    def capability_matrix(self) -> dict[str, dict[str, str]]:
        """Return the granular per-dimension capability matrix.

        A single tool-level ``VERIFIED`` never implies every PoP capability is
        proven (Phase 2.1 directive §4). This returns the per-dimension status
        recorded from real runtime probes; see docs/POP_CAPABILITY_MATRIX.md.

        Tool-level ``status()`` remains the gate for the base ``execute()``
        wrapper and is intentionally separate from this diagnostic matrix.
        """
        return {key: dict(entry) for key, entry in _CAPABILITY_MATRIX.items()}

    def to_sources(self, results: list[dict[str, Any]]) -> list[Source]:
        """Map a list of normalized PoP result dicts into validated ``Source`` records.

        This is the audit A2 remediation: the adapter's ``_normalize()`` output is
        a Source-shaped dict, and ``to_sources()`` routes it through
        :func:`src.tools.source_mapper.source_from_dict` so the result is a real
        ``list[Source]`` with unknown fields preserved in ``metadata``.

        Parameters
        ----------
        results:
            The ``results`` list from a :class:`PublishOrPerishResponse`.
        """
        return [
            source_from_dict(result, origin="publish_or_perish")
            for result in results
            if isinstance(result, dict)
        ]

    def _build_command(self, request: PublishOrPerishRequest, outfile: str | None) -> list[str]:
        """Construct the PoP CLI command from a request.

        Uses ONLY flags observed in ``pop8query --help``. No invented flags.
        """
        exe = self._executable()
        if exe is None:
            raise IntegrationError(
                "Publish or Perish executable not found",
                error_code="EXECUTABLE_NOT_FOUND",
                context={"search_dirs": get_config().tool("publish_or_perish").search_dirs},
            )

        source_flag = POP_SOURCES.get(request.source)
        if source_flag is None:
            raise IntegrationError(
                f"Unknown data source {request.source!r}",
                error_code="UNKNOWN_DATA_SOURCE",
                context={"supported": sorted(POP_SOURCES)},
            )

        cmd: list[str] = [exe, source_flag]

        # Query field mapping (verbatim from --help). Uses the module-level
        # table so the mapping and the error message can never drift apart.
        field_flag = _QUERY_FIELD_FLAGS.get(request.query_field)
        if field_flag is None:
            raise IntegrationError(
                f"Unknown query_field {request.query_field!r}",
                error_code="UNKNOWN_QUERY_FIELD",
                context={"supported": sorted(_QUERY_FIELD_FLAGS)},
            )
        cmd.extend([field_flag, request.query])

        # Year filter: --years from-to (allow open-ended via from- / -to).
        years: str | None = None
        if request.year_start is not None and request.year_end is not None:
            years = f"{request.year_start}-{request.year_end}"
        elif request.year_start is not None:
            years = f"{request.year_start}-"
        elif request.year_end is not None:
            years = f"-{request.year_end}"
        if years is not None:
            cmd.extend(["--years", years])

        cmd.extend(["--max", str(request.max_results)])

        # Optional sort.
        if request.sort:
            cmd.extend(["--sort", request.sort])

        # Choose output format: JSONL is the most reliable for programmatic
        # normalization (one JSON object per line, no quoting ambiguity).
        cmd.extend(["--format", "jsonl"])

        if outfile:
            cmd.append(outfile)

        return cmd

    def _parse_jsonl(self, text: str) -> list[dict[str, Any]]:
        """Parse JSONL output into a list of record dicts, skipping bad lines.

        Only lines that parse as JSON objects are kept. Malformed lines are
        counted and logged but never fabricated.
        """
        records: list[dict[str, Any]] = []
        skipped = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(data, dict):
                records.append(data)
        if skipped:
            _logger.warning(
                "PoP JSONL parse skipped malformed lines",
                extra={"tool": self.name, "skipped": skipped},
            )
        return records

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw PoP record into the internal ``Source``-shape.

        Only fields that actually appeared in the real Crossref output are
        mapped. Missing values stay ``None``; values are NEVER invented.
        """
        authors = raw.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        elif isinstance(authors, list):
            # OpenAlex returns authors as dicts ({name, affiliation}), while
            # Crossref returns plain strings. Normalize both to name strings so
            # the internal Source shape is consistent regardless of datasource.
            flattened: list[str] = []
            for entry in authors:
                if isinstance(entry, str):
                    flattened.append(entry)
                elif isinstance(entry, dict) and entry.get("name"):
                    flattened.append(str(entry["name"]))
            authors = flattened

        article_url = raw.get("article_url") or raw.get("url")
        doi = raw.get("doi")
        return {
            "title": raw.get("title"),
            "authors": authors,
            "year": raw.get("year"),
            "venue": raw.get("source"),          # PoP calls it 'source' (journal)
            "doi": doi,
            "url": article_url,
            "abstract": raw.get("abstract"),
            "source_origin": "publish_or_perish",
            "source_type": raw.get("type"),
            "publisher": raw.get("publisher"),
            "issn": raw.get("issn"),
            "volume": raw.get("volume"),
            "issue": raw.get("issue"),
            "pages": (
                f"{raw.get('startpage')}-{raw.get('endpage')}"
                if raw.get("startpage") is not None and raw.get("endpage") is not None
                else None
            ),
            "cited_by": raw.get("cites"),
            "rank": raw.get("rank"),
            # Preserve the raw record for full-fidelity audit (never drop data).
            "_raw": raw,
        }

    def _execute(self, request: PublishOrPerishRequest) -> PublishOrPerishResponse:
        """Run a real PoP search and normalize the result.

        Raises
        ------
        IntegrationError
            For missing executable/unknown source, or when the subprocess exits
            non-zero (carrying real stderr for diagnosis).
        """
        exe = self._executable()
        if exe is None:
            return self.response_model.failure(
                error_code="EXECUTABLE_NOT_FOUND",
                error_message="Publish or Perish executable not found on this system",
                status=IntegrationStatus.NOT_IMPLEMENTED,
                results=[],
                result_count=0,
                raw_count=0,
                query_used=request.query,
                datasource="",
                command="",
                exit_code=None,
                detected_format="",
                raw_output_text="",
            )

        # Write JSONL to a temp file (avoid quoting pitfalls of stdout redirect).
        with tempfile.TemporaryDirectory() as tmp:
            outfile = str(Path(tmp) / "pop_results.jsonl")
            cmd = self._build_command(request, outfile=outfile)
            timeout = request.timeout_seconds or get_config().tool("publish_or_perish").timeout_seconds

            self._logger.info(
                "PoP search invoked",
                extra={"tool": self.name, "command": " ".join(cmd)},
            )
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                    # Windows: without DEVNULL stdin, subprocess tries to inherit
                    # an invalid stdin handle and raises WinError 6.
                    stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired as exc:
                return self.response_model.failure(
                    error_code="TIMEOUT",
                    error_message=f"PoP search timed out after {timeout}s",
                    status=self.status(),
                    results=[],
                    result_count=0,
                    raw_count=0,
                    query_used=request.query,
                    datasource=request.source,
                    command=" ".join(cmd),
                    exit_code=None,
                    detected_format="jsonl",
                    raw_output_text=exc.stdout or "",
                )

            stdout_text = proc.stdout or ""
            stderr_text = proc.stderr or ""

            # PoP writes the results to the outfile, so read from there first.
            # PoP emits a UTF-8 BOM; decoding as utf-8-sig strips it so the first
            # line parses cleanly as JSON.
            raw_records: list[dict[str, Any]] = []
            if Path(outfile).is_file():
                file_text = Path(outfile).read_text(encoding="utf-8-sig", errors="replace")
                raw_records = self._parse_jsonl(file_text)

            parsed_text = "".join(raw_records and [json.dumps(r) + "\n" for r in raw_records] or [])

            # If the process failed but we still got output, surface it honestly.
            if proc.returncode != 0:
                message = stderr_text.strip() or stdout_text.strip() or f"exit code {proc.returncode}"
                return self.response_model.failure(
                    error_code=f"POP_EXIT_{proc.returncode}",
                    error_message=f"PoP search failed: {message}",
                    status=self.status(),
                    results=[],
                    result_count=0,
                    raw_count=len(raw_records),
                    query_used=request.query,
                    datasource=request.source,
                    command=" ".join(cmd),
                    exit_code=proc.returncode,
                    detected_format="jsonl",
                    raw_output_text=parsed_text[:4000],
                )

            normalized = [self._normalize(r) for r in raw_records]
            # Only count records that have at least a title (minimal validity).
            valid = [n for n in normalized if n.get("title")]

            # Enforce max_results locally: some datasources (Semantic Scholar)
            # ignore --max and return everything. raw_count still reports the
            # true number returned; result_count honours the requested cap.
            if len(valid) > request.max_results:
                self._logger.warning(
                    "PoP returned more records than requested; truncating",
                    extra={
                        "tool": self.name,
                        "returned": len(valid),
                        "max_results": request.max_results,
                    },
                )
                valid = valid[: request.max_results]

            self._logger.info(
                "PoP search completed",
                extra={
                    "tool": self.name,
                    "raw": len(raw_records),
                    "normalized": len(valid),
                    "exit_code": proc.returncode,
                },
            )

            return PublishOrPerishResponse(
                success=True,
                results=valid,
                result_count=len(valid),
                raw_count=len(raw_records),
                query_used=request.query,
                datasource=request.source,
                command=" ".join(cmd),
                exit_code=proc.returncode,
                detected_format="jsonl",
                raw_output_text=parsed_text[:4000],
                status=self.status(),
            )
