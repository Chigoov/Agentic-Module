"""Task state schema.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §8 — task state machine.
  * WORKFLOW.md §1 — Academic Writing Mode states.
  * WORKFLOW.md §2 — Deep Research Mode states.

A :class:`Task` is the root container for a research project. It holds the
user's request, the research plan, the chosen mode, and the current workflow
state. Subworkflows (discovery, verification, etc.) reference the task by ID.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from src.core.errors import StateTransitionError
from src.schemas.base import BaseRecord

__all__ = [
    "TaskState",
    "ResearchMode",
    "Task",
    "is_terminal_state",
    "is_failure_state",
]


class TaskState(StrEnum):
    """Workflow states from 00_MASTER_INSTRUCTION.md §8."""

    CREATED = "CREATED"
    PLANNED = "PLANNED"
    RESEARCHING = "RESEARCHING"
    VERIFYING = "VERIFYING"
    RETRIEVING = "RETRIEVING"
    EXTRACTING = "EXTRACTING"
    SYNTHESIZING = "SYNTHESIZING"
    WRITING = "WRITING"
    AUDITING = "AUDITING"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"

    # Non-success states requiring intervention or retry
    NEEDS_RESEARCH = "NEEDS_RESEARCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NEEDS_REVISION = "NEEDS_REVISION"
    FAILED = "FAILED"


class ResearchMode(StrEnum):
    """Research depth from WORKFLOW.md §1/§2."""

    ACADEMIC_WRITING = "ACADEMIC_WRITING"
    DEEP_RESEARCH = "DEEP_RESEARCH"


#: Terminal states: the workflow has stopped and will not resume automatically.
TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.NEEDS_REVIEW,
    }
)

#: Failure states: the task did not complete successfully.
FAILURE_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.FAILED,
        TaskState.NEEDS_REVIEW,
        TaskState.NEEDS_REVISION,
    }
)


def is_terminal_state(state: TaskState | str) -> bool:
    return TaskState(state) in TERMINAL_STATES


def is_failure_state(state: TaskState | str) -> bool:
    return TaskState(state) in FAILURE_STATES


class Task(BaseRecord):
    """Root container for a research project.

    Attributes
    ----------
    user_request:
        Original user request text.
    mode:
        Chosen research mode (academic writing or deep research).
    state:
        Current workflow position.
    workspace:
        Name of the project workspace (e.g. "TUGAS 1").
    project_dir:
        Absolute path to the project folder inside the workspace.
    research_plan:
        Structured plan from ResearchPlannerAgent (may be empty until PLANNED).
    config:
        Task-specific configuration overrides.
    """

    id_prefix: str = Field(default="task", exclude=True, repr=False)

    user_request: str
    mode: ResearchMode = ResearchMode.ACADEMIC_WRITING
    state: TaskState = TaskState.CREATED
    workspace: str
    project_dir: str
    research_plan: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    def transition_to(self, new_state: TaskState, *, reason: str, actor: str | None = None) -> None:
        """Transition to ``new_state``, recording the change in the history.

        Raises
        ------
        StateTransitionError
            If the transition is not allowed by the workflow rules.
        """
        old_state = self.state

        # Validate the transition (basic checks; a real workflow engine would
        # encode a full graph). Phase 1 accepts any transition for flexibility.
        if old_state == new_state:
            raise StateTransitionError(
                f"Task {self.id} is already in state {old_state}",
                task_id=self.id,
                state=str(old_state),
            )

        # Record the transition before mutating state so the history is accurate
        # even if downstream code raises.
        self.record_transition(
            from_state=str(old_state), to_state=str(new_state), reason=reason, actor=actor
        )
        self.state = new_state

    def mark_completed(self, *, reason: str = "All workflow stages passed") -> None:
        """Convenience method to transition to COMPLETED."""
        self.transition_to(TaskState.COMPLETED, reason=reason, actor="system")

    def mark_failed(self, *, reason: str, recoverable: bool = False) -> None:
        """Convenience method to transition to FAILED and attach an error."""
        self.record_error(code="TASK_FAILED", message=reason, recoverable=recoverable)
        self.transition_to(TaskState.FAILED, reason=reason, actor="system")

    def request_review(self, *, reason: str) -> None:
        """Escalate to NEEDS_REVIEW per WORKFLOW.md §3."""
        self.transition_to(TaskState.NEEDS_REVIEW, reason=reason, actor="system")
