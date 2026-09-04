"""AUTONOMI AGENTIC ILMIAH — system package.

SYSTEM_ROOT is the ``DATA BASE`` directory that contains this package.
See ``00_MASTER_INSTRUCTION.md`` for the authoritative specification.

Layering (SYSTEM_RULES.md §B):
    core        deterministic infrastructure (paths, config, logging, storage)
    context     deterministic context selection/priority (minimal LLM context)
    schemas     machine-readable data contracts
    tools       external capabilities + provider adapters
    agents      reasoning components
    workflows   explicit state machines
    runtime     bootstrap and system context
"""

from __future__ import annotations

__all__ = ["SYSTEM_NAME", "SPEC_VERSION", "BUILD_PHASE", "__version__"]

SYSTEM_NAME = "AUTONOMI AGENTIC ILMIAH"

#: Version of the specification documents in SYSTEM_ROOT that this code targets.
SPEC_VERSION = "1.0"

#: Highest BUILD_PLAN.md phase that is implemented and tested.
BUILD_PHASE = 3

__version__ = "1.0.0"
