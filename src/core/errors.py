"""System error hierarchy.

Errors are part of the contract of every component (00_MASTER_INSTRUCTION.md §6
requires explicit error states). Callers should be able to distinguish
"capability missing" from "capability broken" from "human decision required".
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AutonomiError",
    "ConfigurationError",
    "PathSafetyError",
    "SchemaValidationError",
    "StateTransitionError",
    "ProjectError",
    "IntegrationError",
    "CapabilityNotImplementedError",
    "CapabilityNotConfiguredError",
    "CapabilityUnavailableError",
    "HumanReviewRequired",
]


class AutonomiError(Exception):
    """Base class for every error raised by this system."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        if not self.context:
            return self.message
        rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(self.context.items()))
        return f"{self.message} ({rendered})"

    def to_dict(self) -> dict[str, Any]:
        return {"error": type(self).__name__, "message": self.message, "context": self.context}


class ConfigurationError(AutonomiError):
    """Configuration is missing, malformed, or internally inconsistent."""


class PathSafetyError(AutonomiError):
    """An operation targeted a path outside its permitted boundary.

    Raised instead of performing writes that could damage user work
    (SYSTEM_RULES.md §A.6/§A.7).
    """


class SchemaValidationError(AutonomiError):
    """Structured data failed its contract."""


class StateTransitionError(AutonomiError):
    """An illegal state machine transition was attempted."""


class ProjectError(AutonomiError):
    """Project lifecycle failure (creation, loading, or metadata integrity)."""


class IntegrationError(AutonomiError):
    """Base class for external capability failures."""


class CapabilityNotImplementedError(IntegrationError, NotImplementedError):
    """The capability is declared but has no implementation yet.

    Deliberately also a :class:`NotImplementedError` so that accidental use in
    a workflow fails loudly rather than silently returning empty results.
    """


class CapabilityNotConfiguredError(IntegrationError):
    """The capability exists but required configuration/credentials are absent."""


class CapabilityUnavailableError(IntegrationError):
    """The capability is configured but could not be reached in this environment."""


class HumanReviewRequired(AutonomiError):
    """A consequential ambiguity must be escalated to the user.

    Carries the structured decision request mandated by WORKFLOW.md §3.
    """

    def __init__(
        self,
        issue: str,
        *,
        context: str,
        why_it_matters: str,
        options: list[str],
        recommended_action: str | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(issue, **extra)
        self.issue = issue
        self.review_context = context
        self.why_it_matters = why_it_matters
        self.options = list(options)
        self.recommended_action = recommended_action

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "issue": self.issue,
                "review_context": self.review_context,
                "why_it_matters": self.why_it_matters,
                "options": self.options,
                "recommended_action": self.recommended_action,
            }
        )
        return payload

    def render(self) -> str:
        """Render the decision request in the format required by WORKFLOW.md §3."""
        lines = [
            f"ISSUE: {self.issue}",
            f"CONTEXT: {self.review_context}",
            f"WHY IT MATTERS: {self.why_it_matters}",
            "OPTIONS:",
        ]
        lines.extend(f"  {index}. {option}" for index, option in enumerate(self.options, start=1))
        lines.append(f"RECOMMENDED ACTION: {self.recommended_action or 'none proposed'}")
        return "\n".join(lines)
