"""Source retrieval tool for roadmap Phase 6 with Direct Download (Bagian D).

Retrieval handles:
1. Direct download for open access ebooks/PDFs with rights verification.
2. Abstract persistence when available.
3. Web page / HTML retrieval with standard library parsing.
4. Page-aware PDF parsing preserving provenance without guessing text.
5. Atomic writes, hash verification, file size limits, and path safety.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import urllib.request
import urllib.parse
import ipaddress
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from pydantic import Field

from src.core.storage import backup_file, ensure_within
from src.schemas.evidence import ReadingDepth
from src.schemas.project import Project
from src.schemas.source import AccessMode, RetrievalStatus, RightsStatus, Source, SourceState, SourceType
from src.tools.base import BaseTool, ToolRequest, ToolResponse
from src.tools.pdf_parser import PDFParserTool
from src.tools.http_client import read_bounded

__all__ = [
    "RetrievedPayload",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievalTool",
    "safe_source_filename",
]


def safe_source_filename(source: Source, suffix: str) -> str:
    """Generate a clean, deterministic filename inside source_documents/."""
    clean_suffix = re.sub(r"[^a-zA-Z0-9]", "", suffix).lower() or "txt"
    if source.source_type == SourceType.BOOK and source.title:
        slug = re.sub(r"[^\w\s-]", "", source.title).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")[:60]
        if slug:
            return f"{slug}.{clean_suffix}"
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", source.id)
    return f"{safe_id}.{clean_suffix}"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored = 0
        self.primary_titles: list[str] = []
        self._title_parts = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._ignored += 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section", "article", "br"}:
            self.parts.append("\n")
            if tag == "h1":
                self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._title_parts is not None:
            self.primary_titles.append(" ".join(self._title_parts))
            self._title_parts = None
        if tag in {"script", "style"}:
            self._ignored = max(0, self._ignored - 1)
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and not self._ignored:
            self.parts.append(text)
            if self._title_parts is not None:
                self._title_parts.append(text)

    def text(self) -> str:
        return "\n".join(" ".join(line.split()) for line in " ".join(self.parts).splitlines() if line.strip())


@dataclass(frozen=True)
class RetrievedPayload:
    content: bytes
    content_type: str = "text/plain"
    final_url: str | None = None


class RetrievalRequest(ToolRequest):
    project: Project
    source: Source
    timeout_seconds: int = Field(default=30, ge=1)
    direct_download: bool = False
    download_url: str | None = None
    max_file_size_bytes: int = Field(default=50 * 1024 * 1024, ge=1)  # 50 MiB default
    allow_overwrite: bool = False
    allow_direct_download: bool = True


class RetrievalResponse(ToolResponse):
    source: Source | None = None
    document_path: str | None = None
    parsed_text: str | None = None
    retrieval_method: str | None = None


Fetcher = Callable[[str, int], RetrievedPayload]


def _public_destination(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Retrieval requires an http/https URL without credentials")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Retrieval destination must resolve exclusively to public IP addresses")


class _PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        _public_destination(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _open_download_rights(source: Source) -> bool:
    return source.access_mode == AccessMode.OPEN_DOWNLOAD and source.rights_status in {
        RightsStatus.PUBLIC_DOMAIN, RightsStatus.OPEN_LICENSE, RightsStatus.PROVIDER_STATED_FREE,
    }


class RetrievalTool(BaseTool[RetrievalRequest, RetrievalResponse]):
    """Retrieve available source content and update the source record."""

    response_model = RetrievalResponse
    tool_name = "retrieval"

    def __init__(self, *, fetcher: Fetcher | None = None) -> None:
        super().__init__()
        self._fetcher = fetcher

    def _fetch(self, url: str, request: RetrievalRequest) -> RetrievedPayload:
        if self._fetcher:
            return self._fetcher(url, request.timeout_seconds)
        return self._fetch_url(url, request.timeout_seconds, request.max_file_size_bytes)

    def _execute(self, request: RetrievalRequest) -> RetrievalResponse:
        if request.project is None or not isinstance(request.project, Project):
            return RetrievalResponse.failure(
                error_code="NO_ACTIVE_PROJECT",
                error_message="Active project is required for retrieval operations",
                source=request.source,
            )

        try:
            from src.core.paths import get_paths
            paths = get_paths()
            proj_dir = request.project.directory.resolve()
            if paths.is_inside_system_root(proj_dir):
                return RetrievalResponse.failure(
                    error_code="INVALID_PROJECT_CONTEXT",
                    error_message=f"Project directory cannot be inside SYSTEM_ROOT (DATA BASE): {proj_dir}",
                    source=request.source,
                )
            if proj_dir == paths.workspace_root.resolve():
                return RetrievalResponse.failure(
                    error_code="INVALID_PROJECT_CONTEXT",
                    error_message=f"Project directory cannot be the root repository: {proj_dir}",
                    source=request.source,
                )
        except Exception as exc:
            return RetrievalResponse.failure(
                error_code="INVALID_PROJECT_CONTEXT",
                error_message=str(exc),
                source=request.source,
            )

        source = request.source
        if source.state is SourceState.REJECTED:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(code="SOURCE_REJECTED", message="Rejected sources are not retrievable")
            return RetrievalResponse.failure(
                error_code="SOURCE_REJECTED",
                error_message="Rejected sources are not retrievable",
                source=source,
            )

        # Decide whether to execute direct download
        wants_direct_dl = request.direct_download or bool(request.download_url)
        has_downloads = bool(source.download_urls) and source.download_allowed and not source.abstract

        if request.allow_direct_download and (wants_direct_dl or has_downloads):
            return self._execute_direct_download(request)

        # Fallback to abstract if available
        if source.abstract:
            parsed_text = self._parse_document(source, RetrievedPayload(source.abstract.encode("utf-8")), "abstract")
            path = self._write_text(request.project, source, "abstract", source.abstract)
            method = "abstract"
            if source.reading_depth == ReadingDepth.UNAVAILABLE:
                source.update_reading_depth(ReadingDepth.ABSTRACT_ONLY, reason="Persisted abstract content", actor=self.name)
        elif source.url:
            try:
                payload = self._fetch(source.url, request)
            except Exception as exc:
                source.retrieval_status = RetrievalStatus.FAILED
                source.record_error(code="URL_FETCH_FAILED", message=f"Failed to fetch {source.url}: {exc}")
                return RetrievalResponse.failure(
                    error_code="URL_FETCH_FAILED",
                    error_message=f"Failed to fetch {source.url}: {exc}",
                    source=source,
                )

            if not payload.content:
                source.retrieval_status = RetrievalStatus.FAILED
                source.record_error(code="EMPTY_CONTENT", message=f"Content fetched from {source.url} is empty (0 bytes)")
                return RetrievalResponse.failure(
                    error_code="EMPTY_CONTENT",
                    error_message=f"Content fetched from {source.url} is empty (0 bytes)",
                    source=source,
                )

            if len(payload.content) > request.max_file_size_bytes:
                return RetrievalResponse.failure(error_code="FILE_SIZE_EXCEEDED",
                    error_message="Retrieved content exceeds byte limit", source=source)

            if ("pdf" in payload.content_type.lower() or payload.content.startswith(b"%PDF") or source.url.lower().endswith(".pdf")) and not _open_download_rights(source):
                return self._refuse_download(request=request, code="DOWNLOAD_RIGHTS_UNCLEAR",
                    reason="Generic PDF route requires the same open-download rights as direct download",
                    recommended_action="Confirm license and access rights", severity="HIGH")

            suffix = "pdf" if payload.content.startswith(b"%PDF") else self._suffix(payload.content_type, source.url)
            try:
                parsed_text = self._parse_document(source, payload, suffix)
            except ValueError as exc:
                return RetrievalResponse.failure(error_code="PDF_PARSE_FAILED", error_message=str(exc), source=source)
            sha256_hash = hashlib.sha256(payload.content).hexdigest()
            path = self._write_bytes_with_safety(
                request.project,
                source,
                suffix,
                payload.content,
                sha256_hash,
                allow_overwrite=request.allow_overwrite,
            )
            method = "url"
            source.metadata["retrieval_final_url"] = payload.final_url or source.url
        else:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(code="NO_RETRIEVABLE_CONTENT", message="Source has neither abstract nor URL")
            return RetrievalResponse.failure(
                error_code="NO_RETRIEVABLE_CONTENT",
                error_message="Source has neither abstract nor URL",
                source=source,
            )

        source.metadata["retrieval"] = {
            "retrieval_method": method, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "retrieved_at": datetime.now(UTC).isoformat(), "origin": source.provider or "caller abstract snapshot",
            "final_url": source.metadata.get("retrieval_final_url") or source.url,
        }
        source.retrieval_path = str(path)
        source.metadata["file_path"] = f"source_documents/{Path(path).name}"
        if source.source_type == SourceType.BOOK:
            source.metadata["source_type"] = "book"
            source.metadata["title"] = source.title
            source.metadata["download_url"] = source.url or (source.download_urls[0] if source.download_urls else None)
        source.retrieval_status = RetrievalStatus.RETRIEVED
        content_verified = self._check_article_content(request) if method != "abstract" else True
        if method != "abstract" and content_verified and source.state not in {SourceState.FULLTEXT_RETRIEVED, SourceState.APPROVED}:
            source.transition_to(
                SourceState.FULLTEXT_RETRIEVED,
                reason=f"Retrieved source content via {method}",
                actor=self.name,
            )

        return RetrievalResponse(
            source=source,
            document_path=str(path),
            parsed_text=parsed_text,
            retrieval_method=method,
            metadata={"content_parsed": parsed_text is not None, "source_content": source.metadata.get("content_verification")},
        )

    def _refuse_download(
        self,
        *,
        request: RetrievalRequest,
        code: str,
        reason: str,
        recommended_action: str,
        severity: str = "HIGH",
    ) -> RetrievalResponse:
        source = request.source
        source.retrieval_status = RetrievalStatus.FAILED
        source.retrieval_path = None
        source.record_error(code=code, message=reason)
        if source.state != SourceState.NEEDS_HUMAN_REVIEW:
            source.request_review(reason=reason)

        if request.project:
            try:
                from src.schemas.project import ProjectArtifact
                from src.schemas.review import ReviewItem, ReviewQueue

                queue_path = request.project.artifact_path(ProjectArtifact.REVIEW_QUEUE)
                queue = ReviewQueue.load(queue_path)
                queue.add(
                    ReviewItem(
                        item_type="source",
                        item_id=source.id,
                        severity=severity,
                        reason=reason,
                        recommended_action=recommended_action,
                    )
                )
                queue.save(queue_path, root=request.project.directory)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to enqueue review item for source %s: %s", source.id, exc
                )

        return RetrievalResponse.failure(
            error_code=code,
            error_message=reason,
            source=source,
        )

    def _execute_direct_download(self, request: RetrievalRequest) -> RetrievalResponse:
        source = request.source

        # 1. Strict access mode validation
        if source.access_mode == AccessMode.BORROW_ONLY:
            return self._refuse_download(
                request=request,
                code="BORROW_ONLY_DOWNLOAD_FORBIDDEN",
                reason=f"Borrow-only resource '{source.title}' cannot be downloaded automatically",
                recommended_action="Access digital loan from provider site or library catalog",
                severity="HIGH",
            )

        if source.access_mode == AccessMode.PREVIEW_ONLY:
            return self._refuse_download(
                request=request,
                code="PREVIEW_ONLY_DOWNLOAD_FORBIDDEN",
                reason=f"Preview-only resource '{source.title}' cannot be downloaded automatically",
                recommended_action="Inspect preview online on provider site",
                severity="MEDIUM",
            )

        # 2. Strict rights status and open download authorization
        # Rule: UNKNOWN, BORROW_ONLY, PREVIEW_ONLY, RESTRICTED are forbidden.
        # Only OPEN_DOWNLOAD with PUBLIC_DOMAIN, OPEN_LICENSE, or PROVIDER_STATED_FREE is permitted.
        # Providing an explicit request.download_url CANNOT bypass these rights checks.
        if not _open_download_rights(source):
            code = (
                "DOWNLOAD_RIGHTS_UNCLEAR"
                if source.rights_status == RightsStatus.UNKNOWN or source.access_mode == AccessMode.UNKNOWN
                else "DOWNLOAD_RIGHTS_RESTRICTED"
            )
            reason = f"Direct download forbidden: access_mode={source.access_mode}, rights_status={source.rights_status}"
            return self._refuse_download(
                request=request,
                code=code,
                reason=reason,
                recommended_action="Confirm license and rights from provider landing page before downloading",
                severity="HIGH",
            )

        target_url = request.download_url or (source.download_urls[0] if source.download_urls else None)
        if not target_url:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(code="NO_DOWNLOAD_URL", message="No download URL available for direct download")
            return RetrievalResponse.failure(
                error_code="NO_DOWNLOAD_URL",
                error_message="No download URL available for direct download",
                source=source,
            )

        # Ensure target_url is tracked on source
        if target_url not in source.download_urls:
            source.download_urls.append(target_url)

        # 3. Fetch content
        try:
            payload = self._fetch(target_url, request)
        except Exception as exc:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(code="DOWNLOAD_FAILED", message=f"Failed to download from {target_url}: {exc}")
            return RetrievalResponse.failure(
                error_code="DOWNLOAD_FAILED",
                error_message=f"Failed to download from {target_url}: {exc}",
                source=source,
            )

        # 3. Content validation
        if not payload.content or len(payload.content) == 0:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(code="EMPTY_CONTENT", message=f"Downloaded file from {target_url} is empty (0 bytes)")
            return RetrievalResponse.failure(
                error_code="EMPTY_CONTENT",
                error_message=f"Downloaded file from {target_url} is empty (0 bytes)",
                source=source,
            )

        if len(payload.content) > request.max_file_size_bytes:
            source.retrieval_status = RetrievalStatus.FAILED
            source.record_error(
                code="FILE_SIZE_EXCEEDED",
                message=f"File size {len(payload.content)} exceeds maximum limit {request.max_file_size_bytes}",
            )
            return RetrievalResponse.failure(
                error_code="FILE_SIZE_EXCEEDED",
                error_message=f"File size {len(payload.content)} exceeds maximum limit {request.max_file_size_bytes}",
                source=source,
            )

        # 4. Hash and path safety
        sha256_hash = hashlib.sha256(payload.content).hexdigest()
        suffix = "pdf" if payload.content.startswith(b"%PDF") else self._suffix(payload.content_type, target_url)

        # 5. Parse document (page-aware for PDF)
        try:
            parsed_text = self._parse_document(source, payload, suffix)
        except ValueError as exc:
            return RetrievalResponse.failure(error_code="PDF_PARSE_FAILED", error_message=str(exc), source=source)

        # 6. Record retrieval metadata
        path = self._write_bytes_with_safety(request.project, source, suffix, payload.content,
            sha256_hash, allow_overwrite=request.allow_overwrite)
        retrieval_meta = {
            "retrieval_method": "direct_download",
            "content_type": payload.content_type,
            "download_size_bytes": len(payload.content),
            "sha256": sha256_hash,
            "final_url": payload.final_url or target_url,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "rights_status": str(source.rights_status),
            "landing_url": source.landing_url or source.url,
            "download_url": target_url,
        }
        retrieval_meta["pdf_page_count"] = len(source.metadata["pdf_pages"])

        source.metadata["retrieval"] = retrieval_meta
        source.metadata["file_path"] = f"source_documents/{Path(path).name}"
        if source.source_type == SourceType.BOOK:
            source.metadata["source_type"] = "book"
            source.metadata["title"] = source.title
            source.metadata["download_url"] = target_url
        source.retrieval_path = str(path)
        source.retrieval_status = RetrievalStatus.RETRIEVED
        content_verified = self._check_article_content(request)
        if content_verified and source.state not in {SourceState.FULLTEXT_RETRIEVED, SourceState.APPROVED}:
            source.transition_to(
                SourceState.FULLTEXT_RETRIEVED,
                reason="Retrieved full-text via direct_download",
                actor=self.name,
            )

        return RetrievalResponse(
            source=source,
            document_path=str(path),
            parsed_text=parsed_text,
            retrieval_method="direct_download",
            metadata={
                "content_parsed": parsed_text is not None,
                "source_content": source.metadata.get("content_verification"),
                **retrieval_meta,
            },
        )

    @staticmethod
    def _check_article_content(request):
        if request.source.source_type in {SourceType.BOOK, SourceType.BOOK_CHAPTER}:
            source = request.source
            allowed = (source.access_mode in {AccessMode.OPEN_DOWNLOAD, AccessMode.READ_ONLINE}
                and source.rights_status in {RightsStatus.PUBLIC_DOMAIN, RightsStatus.OPEN_LICENSE, RightsStatus.PROVIDER_STATED_FREE}
                and Path(source.retrieval_path or "").suffix.lower() == ".pdf"
                and bool(source.metadata.get("pdf_pages"))
                and source.metadata.get("parsed_readable") is True
                and not source.metadata.get("unreadable_pages"))
            source.metadata["content_verification"] = {"full_text": allowed,
                "basis": "readable_pdf_all_pages" if allowed else "landing_page_or_incomplete_content",
                "semantic_assessment": "not_established"}
            if not allowed:
                source.retrieval_status = RetrievalStatus.PARTIAL
                source.metadata["artifact_kind"] = "landing_page_or_incomplete_content"
            return allowed
        from src.tools.source_content import inspect_source
        proof = inspect_source(request.source, request.project.directory)
        if request.source.source_type == SourceType.WEB_RESOURCE and not (
                request.source.access_mode in {AccessMode.OPEN_DOWNLOAD, AccessMode.READ_ONLINE}
                and request.source.rights_status in {RightsStatus.PUBLIC_DOMAIN, RightsStatus.OPEN_LICENSE, RightsStatus.PROVIDER_STATED_FREE}):
            proof["full_text"] = False
            proof["findings"].append("Web resource requires open reading rights")
        request.source.metadata["content_verification"] = {k:v for k,v in proof.items() if k not in {"text", "pages"}}
        if not proof["full_text"]:
            request.source.retrieval_status = RetrievalStatus.PARTIAL
            if request.source.state != SourceState.NEEDS_HUMAN_REVIEW:
                request.source.request_review(reason="; ".join(proof["findings"]))
        return proof["full_text"]

    def _parse_document(self, source, payload, suffix):
        # Replace parse evidence for every artifact, including empty/failing results.
        source.metadata.update(pdf_pages=[], unreadable_pages=[], parsed_readable=False,
            content_verification={"full_text": False, "basis": "current_artifact_not_verified"})
        source.metadata.pop("artifact_kind", None)
        source.metadata.pop("retrieval_final_url", None)
        if suffix == "pdf":
            parsed = PDFParserTool().parse(payload.content)
            if not parsed.success:
                source.retrieval_status = RetrievalStatus.FAILED
                raise ValueError(parsed.error_message or "PDF parse failed")
            source.metadata.update(pdf_pages=[p.to_dict() for p in parsed.pages], unreadable_pages=parsed.unreadable_pages)
            if parsed.ocr_required:
                source.add_verification_note(f"OCR_REQUIRED_OR_BLANK: Pages {parsed.unreadable_pages} require inspection")
            text = parsed.full_text or None
        else:
            text = self._parse(payload)
        source.metadata["parsed_readable"] = bool(text)
        return text

    @staticmethod
    def _fetch_url(url: str, timeout_seconds: int, max_bytes: int = 50 * 1024 * 1024) -> RetrievedPayload:
        _public_destination(url)
        opener = urllib.request.build_opener(_PublicRedirect())
        with opener.open(url, timeout=timeout_seconds) as response:
            content_type = response.headers.get("content-type", "application/octet-stream")
            return RetrievedPayload(
                content=read_bounded(response, max_bytes),
                content_type=content_type,
                final_url=response.geturl(),
            )

    @staticmethod
    def _parse(payload: RetrievedPayload) -> str | None:
        content_type = payload.content_type.lower()
        text = payload.content.decode(_charset(content_type), errors="replace")
        if "html" not in content_type:
            return text
        parser = _TextExtractor()
        parser.feed(text)
        return parser.text()

    @staticmethod
    def _suffix(content_type: str, url: str) -> str:
        content_type = content_type.lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return "pdf"
        if "html" in content_type:
            return "html"
        return "txt"

    @staticmethod
    def _path(project: Project, source: Source, suffix: str) -> Path:
        filename = safe_source_filename(source, suffix)
        return project.source_path(filename)

    def _write_text(self, project: Project, source: Source, suffix: str, text: str) -> Path:
        return self._write_bytes_with_safety(
            project, source, suffix, text.encode("utf-8"), hashlib.sha256(text.encode("utf-8")).hexdigest()
        )

    def _write_bytes_with_safety(
        self,
        project: Project,
        source: Source,
        suffix: str,
        content: bytes,
        sha256_hash: str,
        allow_overwrite: bool = False,
    ) -> Path:
        target = self._path(project, source, suffix)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            existing_bytes = target.read_bytes()
            if hashlib.sha256(existing_bytes).hexdigest() == sha256_hash:
                return target
            if not allow_overwrite:
                backup_file(target, root=project.directory)

        handle, temp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
        )
        temp_path = os.fspath(temp_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except BaseException:
            try:
                os.unlink(temp_path)
            finally:
                raise
        return target


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    return match.group(1) if match else "utf-8"
