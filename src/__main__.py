"""Package entry point.

Allows running the bootstrap/health check as ``python -m src`` in addition to
``python -m src.runtime.bootstrap``. This gives the system ONE discoverable
CLI surface per M6 of the refactor plan.

Usage:
    python -m src            # full bootstrap
    python -m src --check    # health check only
"""

from __future__ import annotations

import sys

from src.runtime.bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
