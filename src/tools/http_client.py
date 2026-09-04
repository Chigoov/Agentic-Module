"""Minimal HTTP adapter built on the Python standard library.

Specification anchors:
  * ARCHITECTURE.md §2 — external calls happen through tools/adapters.
  * SYSTEM_RULES.md §H.50 — preserve raw external results for auditability.
  * PHASE 3 EXECUTION ADDENDUM §8 — a network/API failure must produce structured
    failure information, never an empty successful result.

The project deliberately avoids adding new third-party dependencies, so this
adapter uses :mod:`urllib.request` rather than ``requests``. It adds the pieces a
research client needs on top of the stdlib: polite ``User-Agent``/``From``
headers, configurable timeouts, bounded retries with exponential backoff and
jitter (only for transient failures), and a structured result that preserves the
raw body (truncated) for auditability.

Failures are raised as :class:`~src.core.errors.IntegrationError`, which the
:class:`~src.tools.base.BaseTool.execute` wrapper converts into a structured
``ToolResponse.failure`` — never into an empty "successful" result.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.core.errors import IntegrationError
from src.core.logging import get_logger

__all__ = [
    "HttpResult",
    "HttpClient",
    "TRANSIENT_STATUS_CODES",
    "build_user_agent",
]

#: Statuses retried with backoff: rate-limiting and server-side transient errors.
TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

#: Upper bound for the preserved raw body (kept truncated, never unlimited).
_MAX_RAW_TEXT = 200_000

#: Maximum number of retry attempts per request (initial call + retries).
_MAX_ATTEMPTS = 5


def build_user_agent(*, contact_email: str | None, version: str = "1.0") -> str:
    """Build a polite User-Agent string, embedding a contact when available."""
    base = f"AUTONOMI-AGENTIC-ILMIAH/{version}"
    if contact_email:
        return f"{base} (mailto:{contact_email})"
    return base


@dataclass
class HttpResult:
    """A successful HTTP response with preserved raw body."""

    url: str
    status: int
    headers: Mapping[str, str]
    text: str
    truncated: bool = False
    elapsed_seconds: float = 0.0

    def json(self) -> Any:
        """Parse the body as JSON, raising a structured error when invalid."""
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise IntegrationError(
                f"{self.url} returned non-JSON content",
                error_code="INVALID_JSON",
                url=self.url,
                status=self.status,
                detail=str(exc),
            ) from exc


class HttpClient:
    """Standard-library HTTP client with politeness, retries, and timeouts."""

    def __init__(
        self,
        *,
        tool_name: str,
        contact_email: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.contact_email = contact_email
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, min(max_retries, _MAX_ATTEMPTS - 1))
        self.extra_headers = dict(extra_headers or {})
        self._logger = get_logger(f"tools.{tool_name}.http")

    def _headers(self, extra: Mapping[str, str] | None) -> dict[str, str]:
        headers = {
            "User-Agent": build_user_agent(contact_email=self.contact_email),
            "Accept": "application/json",
        }
        if self.contact_email:
            headers["From"] = self.contact_email
        headers.update(self.extra_headers)
        if extra:
            headers.update(extra)
        return headers

    def _build_url(self, url: str, params: Mapping[str, Any] | None) -> str:
        if not params:
            return url
        encoded = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
        if not encoded:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{encoded}"

    def request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResult:
        """Perform a GET request with bounded retries for transient failures.

        Raises
        ------
        IntegrationError
            On any non-transient HTTP error, timeout, or connection failure,
            after retries are exhausted. Carries a machine-readable ``error_code``.
        """
        full_url = self._build_url(url, params)
        request_headers = self._headers(headers)

        last_error: Exception | None = None
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                return self._single_request(full_url, request_headers)
            except urllib.error.HTTPError as exc:
                if exc.code in TRANSIENT_STATUS_CODES and attempt <= self.max_retries:
                    last_error = exc
                    self._backoff(attempt, full_url, exc.code)
                    continue
                raise self._to_integration_error(full_url, exc) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt <= self.max_retries:
                    last_error = exc
                    self._backoff(attempt, full_url, None)
                    continue
                raise IntegrationError(
                    f"Request to {full_url} failed: {exc}",
                    error_code="NETWORK_ERROR",
                    url=full_url,
                    detail=str(exc),
                ) from exc

        # Unreachable under normal conditions; kept for defensive completeness.
        raise IntegrationError(
            f"Request to {full_url} failed after {attempt} attempts",
            error_code="NETWORK_ERROR",
            url=full_url,
            detail=str(last_error),
        )

    def _single_request(self, url: str, headers: Mapping[str, str]) -> HttpResult:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError:
            # Re-raised for the caller's retry/error handling to inspect .code.
            raise
        elapsed = time.monotonic() - started

        status = getattr(response, "status", getattr(response, "code", 200))
        body = raw.decode("utf-8", errors="replace")
        truncated = len(body) > _MAX_RAW_TEXT
        if truncated:
            body = body[:_MAX_RAW_TEXT]

        response_headers: dict[str, str] = {
            str(k): str(v) for k, v in dict(response.headers).items()
        }
        return HttpResult(
            url=url,
            status=int(status),
            headers=response_headers,
            text=body,
            truncated=truncated,
            elapsed_seconds=elapsed,
        )

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResult:
        """Perform a GET and return an :class:`HttpResult` whose body is JSON.

        The caller accesses ``result.json()`` for the parsed payload; a non-JSON
        body raises a structured :class:`IntegrationError`.
        """
        result = self.request(url, params=params, headers=headers)
        # Validate JSON eagerly so a malformed body fails here, loudly.
        result.json()
        return result

    def _backoff(self, attempt: int, url: str, status: int | None) -> None:
        delay = (2 ** (attempt - 1)) * (0.5 + random.random())
        self._logger.warning(
            "HTTP request transient failure; retrying",
            extra={
                "tool": self.tool_name,
                "url": url,
                "attempt": attempt,
                "status": status,
                "delay_seconds": round(delay, 3),
            },
        )
        time.sleep(delay)

    def _to_integration_error(self, url: str, exc: urllib.error.HTTPError) -> IntegrationError:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
        except Exception:  # noqa: BLE001 - best-effort body read
            pass
        return IntegrationError(
            f"HTTP {exc.code} from {url}",
            error_code=f"HTTP_{exc.code}",
            url=url,
            status=exc.code,
            detail=detail,
        )
