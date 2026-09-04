"""Generic state machine foundation.

Specification anchors:
  * ARCHITECTURE.md §4 — "The system operates as a state machine where each
    stage produces validated artifacts."
  * 00_MASTER_INSTRUCTION.md §8 — task state machine.
  * WORKFLOW.md §1/§2 — Academic Writing Mode vs Deep Research Mode states.

This module provides a reusable state machine abstraction. Task, Source, and
future orchestration workflows will all be state machines, so factoring out the
transition validation and history recording avoids repeating it in each schema.

Phase 1 creates only the generic machinery; specific workflow orchestrators
(the components that drive tasks through their states) arrive in Phase 3+.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

from src.core.errors import StateTransitionError
from src.core.logging import get_logger

__all__ = [
    "StateMachine",
    "StateEnum",
]

_logger = get_logger(__name__)

StateEnum = TypeVar("StateEnum", bound=Enum)


class StateMachine(ABC, Generic[StateEnum]):
    """Abstract state machine with validated transitions and history.

    Subclasses must implement:
    - :meth:`current_state` property returning the state enum value.
    - :meth:`_apply_transition` which performs the actual mutation.
    - :meth:`_is_valid_transition` which validates proposed transitions.
    - :attr:`_terminal_states` set declaring which states are final.

    Examples
    --------
    Task and Source schemas inherit from BaseRecord (not StateMachine) because
    they are data contracts, but they delegate transition validation to helper
    methods that follow this pattern. Future orchestration workflows that are
    pure logic (not persisted schemas) can subclass StateMachine directly.
    """

    #: States from which no further transitions are permitted.
    _terminal_states: frozenset[StateEnum]

    @property
    @abstractmethod
    def current_state(self) -> StateEnum:
        """The machine's current state."""

    @abstractmethod
    def _apply_transition(
        self, to_state: StateEnum, *, reason: str, actor: str | None
    ) -> None:
        """Mutate the state and record the transition in history."""

    @abstractmethod
    def _is_valid_transition(self, from_state: StateEnum, to_state: StateEnum) -> bool:
        """Whether the transition is permitted by the state machine rules."""

    def transition_to(
        self, new_state: StateEnum, *, reason: str, actor: str | None = None
    ) -> None:
        """Attempt a state transition with validation.

        Parameters
        ----------
        new_state:
            Target state.
        reason:
            Human-readable explanation of why the transition occurred, recorded
            in the audit history.
        actor:
            Component or agent performing the transition.

        Raises
        ------
        StateTransitionError
            When the transition is invalid (same-state, from a terminal state,
            or disallowed by the machine's rules).
        """
        current = self.current_state
        if current == new_state:
            raise StateTransitionError(
                f"Already in state {current}; refusing no-op transition",
                from_state=str(current),
                to_state=str(new_state),
            )
        if current in self._terminal_states:
            raise StateTransitionError(
                f"State {current} is terminal; no further transitions permitted",
                from_state=str(current),
                to_state=str(new_state),
                terminal=True,
            )
        if not self._is_valid_transition(current, new_state):
            raise StateTransitionError(
                f"Transition {current} → {new_state} is not permitted",
                from_state=str(current),
                to_state=str(new_state),
            )

        _logger.debug(
            "State transition",
            extra={
                "from": str(current),
                "to": str(new_state),
                "reason": reason,
                "actor": actor,
            },
        )
        self._apply_transition(new_state, reason=reason, actor=actor)

    def is_terminal(self) -> bool:
        """Whether the machine is in a terminal (final) state."""
        return self.current_state in self._terminal_states

    def can_transition_to(self, target: StateEnum) -> bool:
        """Whether a transition to ``target`` would be permitted right now."""
        current = self.current_state
        if current == target or current in self._terminal_states:
            return False
        return self._is_valid_transition(current, target)
