"""Runtime package — bootstrap and system initialization.

Phase 1 creates the bootstrap entry point that coordinates startup:
1. Path resolution
2. Configuration loading
3. Logging initialization
4. Health check (spec files present, storage writable)
"""

from __future__ import annotations

__all__: list[str] = []
