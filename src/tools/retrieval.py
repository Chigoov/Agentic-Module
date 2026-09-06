"""Source retrieval tool for roadmap Phase 6.

Retrieval is deliberately small: use an existing abstract when available, or
fetch a source URL and persist the raw document under ``source_documents/``.
HTML/plain text are parsed with the standard library; PDF bytes are saved but
not text-parsed here, because claiming PDF text without a parser would be fake.
"""

from __future__ import annotations

import os
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable

from pydantic import Field

from src.core.storage import ensure_within
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.tools.base import BaseTool, ToolRequest, ToolResponse

__all__ = [
    "RetrievedPayload",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievalTool",
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(frozen=True)
class RetrievedPayload:
    content: bytes
    content_type: str = "text/plain"
    final_url: str | None = None


class RetrievalRequest(ToolRequest):
    project: Project
    source: Source
    timeout_seconds: int = Field(default=30, ge=1)


class RetrievalResponse(ToolResponse):
    source: Source | None = None
    document_path: str | None = None
    parsed_text: str | None = None
    retrieval_method: str | None = None


Fetcher = Callable[[str, int], RetrievedPayload]


class RetrievalTool(BaseTool[RetrievalRequest, RetrievalResponse]):
    """Retrieve available source content and update the source record."""

    response_model = RetrievalResponse
    tool_name = "retrieval"

    def __init__(self, *, fetcher: Fetcher | None = None) -> None:
        super().__init__()
        self._fetcher = fetcher or self._fetch_url

    def _execute(self, request: RetrievalRequest) -> RetrievalResponse:
        source = request.source
        if source.state is SourceState.REJECTED:
            return RetrievalResponse.failure(
                error_code="SOURCE_REJECTED",
                error_message="Rejected sources are not retrievable",
                source=source,
            )

        if source.abstract:
            path = self._write_text(request.project, source, "abstract", source.abstract)
            parsed_text = source.abstract
            method = "abstract"
        elif source.url:
            payload = self._fetcher(source.url, request.timeout_seconds)
            parsed_text = self._parse(payload)
            path = self._write_bytes(
                request.project,
                source,
                self._suffix(payload.content_type, source.url),
                payload.content,
            )
            method = "url"
            if payload.final_url and payload.final_url != source.url:
                source.metadata["retrieval_final_url"] = payload.final_url
        else:
            return RetrievalResponse.failure(
                error_code="NO_RETRIEVABLE_CONTENT",
                error_message="Source has neither abstract nor URL",
                source=source,
            )

        source.retrieval_path = str(path)
        if source.state not in {SourceState.FULLTEXT_RETRIEVED, SourceState.APPROVED}:
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
            metadata={"content_parsed": parsed_text is not None},
        )

    @staticmethod
    def _fetch_url(url: str, timeout_seconds: int) -> RetrievedPayload:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            content_type = response.headers.get("content-type", "application/octet-stream")
            return RetrievedPayload(
                content=response.read(),
                content_type=content_type,
                final_url=response.geturl(),
            )

    @staticmethod
    def _parse(payload: RetrievedPayload) -> str | None:
        content_type = payload.content_type.lower()
        if "pdf" in content_type:
            return None
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
    def _path(project: Project, source: Source, suffix: str) -> str:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", source.id)
        return str(project.directory / "source_documents" / f"{safe_id}.{suffix}")

    def _write_text(self, project: Project, source: Source, suffix: str, text: str) -> str:
        return self._write_bytes(project, source, suffix, text.encode("utf-8"))

    def _write_bytes(self, project: Project, source: Source, suffix: str, content: bytes) -> str:
        target = ensure_within(self._path(project, source, suffix), project.directory)
        target.parent.mkdir(parents=True, exist_ok=True)
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
        return str(target)


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    return match.group(1) if match else "utf-8"
