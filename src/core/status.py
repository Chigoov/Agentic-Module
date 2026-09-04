"""Integration status vocabulary.

SYSTEM_RULES.md §H and AGENT_CONSTITUTION.md §23 forbid claiming that an
integration works before it has actually been tested. This module gives the
whole system one shared, explicit vocabulary for that distinction so that a
capability can never be *implicitly* treated as working.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["IntegrationStatus", "USABLE_STATUSES", "is_usable"]


class IntegrationStatus(StrEnum):
    """Lifecycle of an external capability (tool, adapter, provider)."""

    #: No implementation exists yet; calling it must raise.
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

    #: Implementation exists but required configuration/credentials are missing.
    PENDING_CONFIGURATION = "PENDING_CONFIGURATION"

    #: Implemented and configured, but never successfully exercised end-to-end.
    #: Callable, yet the system must not advertise it as proven.
    CONFIGURED = "CONFIGURED"

    #: A real call succeeded in this environment and the result was validated.
    VERIFIED = "VERIFIED"

    #: Deliberately switched off by configuration.
    DISABLED = "DISABLED"

    #: Implemented but failing in this environment.
    FAILED = "FAILED"


#: Statuses in which the system is allowed to actually invoke the capability.
USABLE_STATUSES: frozenset[IntegrationStatus] = frozenset(
    {IntegrationStatus.CONFIGURED, IntegrationStatus.VERIFIED}
)


def is_usable(status: IntegrationStatus | str) -> bool:
    """Return ``True`` only when the capability may be invoked.

    ``VERIFIED`` is the only status that also permits *claiming* the
    integration works.
    """
    return IntegrationStatus(status) in USABLE_STATUSES
