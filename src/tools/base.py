"""Base tool interface.

Specification anchors:
  * ARCHITECTURE.md §2 — tools are capabilities; agents are reasoning.
  * 00_MASTER_INSTRUCTION.md §5 — "A tool performs an external or deterministic operation."
  * ARCHITECTURE.md §5 — "Every tool should have a stable interface and a
    provider-specific implementation."
  * SYSTEM_RULES.md §H.47–§H.49 — never claim an integration works before it
    has actually been tested.

A tool is anything an agent *calls* rather than *contains*. External services
(Publish or Perish, Crossref, model providers), deterministic utilities (PDF
parsing, deduplication), and filesystem operations are all tools. Keeping them
behind one contract lets workflows swap implementations without rewriting logic.

The public :meth:`BaseTool.execute` wrapper is the important part: it refuses to
invoke a capability whose status is not usable, so an unimplemented or
unconfigured tool returns an explicit failure instead of a plausible-looking
empty result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from src.core.errors import IntegrationError
from src.core.logging import get_logger
from src.core.status import IntegrationStatus, is_usable

__all__ = [
    "ToolRequest",
    "ToolResponse",
    "BaseTool",
]


class ToolRequest(BaseModel):
    """Base class for every tool input contract."""

    model_config = ConfigDict(extra="forbid")


class ToolResponse(BaseModel):
    """Base class for every tool output contract.

    Attributes
    ----------
    success:
        Whether the call succeeded. Callers must check this before trusting the
        payload; a failed response may still carry partial data.
    error_code:
        Machine-readable error identifier when ``success`` is ``False``.
    error_message:
        Human-readable explanation when ``success`` is ``False``.
    status:
        Integration status at the time of the call, so audit logs can tell
        "not implemented" apart from "implemented but failed".
    metadata:
        Provider-specific diagnostics preserved for auditability
        (SYSTEM_RULES.md §H.50).
    """

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    error_code: str | None = None
    error_message: str | None = None
    status: IntegrationStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def failure(
        cls,
        *,
        error_code: str,
        error_message: str,
        status: IntegrationStatus | None = None,
        **extra_fields: Any,
    ) -> Self:
        """Build a failure response, filling required subclass fields via ``extra_fields``."""
        return cls(
            success=False,
            error_code=error_code,
            error_message=error_message,
            status=status,
            **extra_fields,
        )


TRequest = TypeVar("TRequest", bound=ToolRequest)
TResponse = TypeVar("TResponse", bound=ToolResponse)


class BaseTool(ABC, Generic[TRequest, TResponse]):
    """Abstract base for every tool/adapter in the system.

    Subclasses must declare :attr:`response_model` (used to build failure
    responses without invoking the tool) and implement :meth:`_execute`.

    Notes
    -----
    ``_execute`` may raise freely: :meth:`execute` converts exceptions into
    structured failure responses so that one broken provider cannot abort an
    entire research run.
    """

    #: Concrete response contract. Declared explicitly rather than introspected
    #: from the Generic parameter so failures never depend on typing internals.
    response_model: ClassVar[type[ToolResponse]] = ToolResponse

    #: Human-readable capability name used in logs and audit reports.
    tool_name: ClassVar[str] = ""

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or self.tool_name or type(self).__name__
        self._logger = get_logger(f"tools.{self.name}")

    # ------------------------------------------------------------------ status
    def status(self) -> IntegrationStatus:
        """Report the current integration status.

        Defaults to ``CONFIGURED``: invokable, but not proven in this
        environment. Only a real, validated call may promote a tool to
        ``VERIFIED`` (SYSTEM_RULES.md §H.49).
        """
        return IntegrationStatus.CONFIGURED

    def is_available(self) -> bool:
        """Whether the tool may currently be invoked."""
        return is_usable(self.status())

    # ----------------------------------------------------------------- calling
    def execute(self, request: TRequest) -> TResponse:
        """Validate status, invoke the tool, and normalize failures.

        Returns
        -------
        TResponse
            Always a response object — never raises for expected failures.
        """
        current = self.status()
        self._logger.debug(
            "Tool invoked",
            extra={"tool": self.name, "status": current.value},
        )

        if not is_usable(current):
            message = {
                IntegrationStatus.NOT_IMPLEMENTED: (
                    f"{self.name} is declared but not implemented yet"
                ),
                IntegrationStatus.PENDING_CONFIGURATION: (
                    f"{self.name} requires configuration before it can be used"
                ),
                IntegrationStatus.DISABLED: f"{self.name} is disabled in configuration",
                IntegrationStatus.FAILED: f"{self.name} is in a failed state",
            }.get(current, f"{self.name} is not usable (status={current.value})")
            self._logger.warning(
                "Tool call refused", extra={"tool": self.name, "status": current.value}
            )
            return self._failure(error_code=current.value, error_message=message, status=current)

        try:
            response = self._execute(request)
        except IntegrationError as exc:
            self._logger.warning(
                "Tool call failed", extra={"tool": self.name, "error": str(exc)}
            )
            return self._failure(
                error_code=str(exc.context.get("error_code", "INTEGRATION_ERROR")),
                error_message=exc.message,
                status=current,
            )
        except Exception as exc:  # noqa: BLE001 - deliberate boundary
            self._logger.error(
                "Tool raised an unhandled exception",
                extra={"tool": self.name, "error": str(exc)},
                exc_info=True,
            )
            return self._failure(
                error_code="INTERNAL_ERROR",
                error_message=f"{self.name} raised an unhandled exception: {exc}",
                status=current,
            )

        if response.status is None:
            response.status = current
        self._logger.info(
            "Tool call completed",
            extra={
                "tool": self.name,
                "success": response.success,
                "error_code": response.error_code,
            },
        )
        return response

    @abstractmethod
    def _execute(self, request: TRequest) -> TResponse:
        """Subclass implementation of the tool's core behaviour."""

    # ----------------------------------------------------------------- helpers
    def _failure(
        self,
        *,
        error_code: str,
        error_message: str,
        status: IntegrationStatus | None = None,
        **extra_fields: Any,
    ) -> TResponse:
        """Construct a failure response using the declared :attr:`response_model`."""
        return self.response_model.failure(  # type: ignore[return-value]
            error_code=error_code,
            error_message=error_message,
            status=status,
            **extra_fields,
        )

    def describe(self) -> dict[str, str]:
        """Diagnostic summary used by the system health report."""
        return {
            "tool": self.name,
            "class": type(self).__name__,
            "status": self.status().value,
        }
