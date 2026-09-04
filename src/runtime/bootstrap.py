"""System bootstrap and health check.

Specification anchor: BUILD_PLAN.md §1 — "Bootstrap orchestrates initialization
of all foundation components before any agent or workflow runs."

Bootstrap is the entry point for:
- Command-line utilities (e.g., ``python -m src.runtime.bootstrap --check``).
- Test fixtures that need a live system.
- Interactive exploration (e.g., ``from src.runtime.bootstrap import bootstrap; bootstrap()``).

The health check validates that:
1. All six specification files are present.
2. Configuration loads without validation errors.
3. Storage directories can be created and written to.
4. No integration is claimed VERIFIED when it hasn't been tested.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.core.config import get_config, load_config
from src.core.logging import get_logger, setup_logging
from src.core.paths import PathResolutionError, SystemPaths, get_paths
from src.core.status import IntegrationStatus

__all__ = [
    "bootstrap",
    "health_check",
    "ensure_storage_dirs",
]

_logger = get_logger(__name__)


def ensure_storage_dirs(paths: SystemPaths) -> None:
    """Create storage directories (logs, cache, runtime, database) when absent.

    Raises
    ------
    OSError
        When a directory cannot be created.
    """
    for directory in [paths.logs_dir, paths.cache_dir, paths.state_dir, paths.database_dir]:
        directory.mkdir(parents=True, exist_ok=True)
        _logger.debug(f"Storage directory ready: {directory}")


def health_check(*, paths: SystemPaths | None = None, verbose: bool = False) -> bool:
    """Validate that the system is ready to run.

    Parameters
    ----------
    paths:
        System paths; discovered when ``None``.
    verbose:
        When ``True``, print diagnostic messages to stdout.

    Returns
    -------
    bool
        ``True`` when all checks pass.
    """
    if paths is None:
        try:
            paths = get_paths()
        except PathResolutionError as exc:
            if verbose:
                print(f"[!] Path resolution failed: {exc}", file=sys.stderr)
            return False

    issues: list[str] = []

    # 1. Spec files present.
    missing = paths.missing_spec_files()
    if missing:
        issues.append(f"Missing specification files: {', '.join(missing)}")

    # 1b. Advisory: supplementary docs absent (never a spec failure).
    missing_supplementary = paths.missing_supplementary_docs()
    if missing_supplementary and verbose:
        print(f"[i] Advisory: missing supplementary docs: {', '.join(missing_supplementary)}", file=sys.stderr)

    # 2. Configuration loads.
    try:
        config = get_config()
    except Exception as exc:
        issues.append(f"Configuration failed to load: {exc}")
        if verbose:
            for issue in issues:
                print(f"[!] {issue}", file=sys.stderr)
        return False

    # 3. Storage writable.
    try:
        ensure_storage_dirs(paths)
        probe = paths.state_dir / ".health_check_probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        issues.append(f"Cannot write to storage directories: {exc}")

    # 4. No integration falsely claimed VERIFIED.
    unverified_verified: list[str] = []
    if config.model_routing.status is IntegrationStatus.VERIFIED:
        if not config.model_routing.api_key:
            unverified_verified.append("model_routing (no API key)")
    for tool_name, tool_config in config.tools.items():
        if (
            tool_config.status is IntegrationStatus.VERIFIED
            and not tool_config.integration_verified
        ):
            unverified_verified.append(f"tools.{tool_name}")
    if unverified_verified:
        issues.append(
            f"Integration(s) marked VERIFIED without testing: {', '.join(unverified_verified)}"
        )

    if issues:
        if verbose:
            for issue in issues:
                print(f"[ERROR] {issue}", file=sys.stderr)
        return False

    if verbose:
        print("[OK] System health check passed")
        print(f"   SYSTEM_ROOT: {paths.system_root}")
        print(f"   WORKSPACE_ROOT: {paths.workspace_root}")
        print(f"   Spec version: {config.system.spec_version}")
        print(f"   Build phase: {config.system.build_phase}")
    return True


def bootstrap(*, verbose: bool = False) -> SystemPaths:
    """Initialize the system: paths → config → logging → health check.

    Parameters
    ----------
    verbose:
        When ``True``, print startup messages to stdout.

    Returns
    -------
    SystemPaths
        Resolved system paths.

    Raises
    ------
    RuntimeError
        When the health check fails.
    """
    if verbose:
        print("[*] Bootstrapping AUTONOMI AGENTIC ILMIAH...")

    # 1. Resolve paths.
    try:
        paths = get_paths()
    except PathResolutionError as exc:
        if verbose:
            print(f"❌ Path resolution failed: {exc}", file=sys.stderr)
        raise RuntimeError("Cannot discover SYSTEM_ROOT") from exc

    # 2. Ensure storage directories exist before logging tries to write.
    try:
        ensure_storage_dirs(paths)
    except OSError as exc:
        if verbose:
            print(f"❌ Storage directory creation failed: {exc}", file=sys.stderr)
        raise RuntimeError("Cannot create storage directories") from exc

    # 3. Load configuration (also cached globally).
    try:
        config = load_config(paths=paths)
    except Exception as exc:
        if verbose:
            print(f"❌ Configuration loading failed: {exc}", file=sys.stderr)
        raise RuntimeError("Cannot load configuration") from exc

    # 4. Initialize logging.
    try:
        setup_logging(config=config, paths=paths)
    except Exception as exc:
        if verbose:
            print(f"❌ Logging setup failed: {exc}", file=sys.stderr)
        raise RuntimeError("Cannot initialize logging") from exc

    _logger.info(
        "Bootstrap complete",
        extra={
            "system_root": str(paths.system_root),
            "workspace_root": str(paths.workspace_root),
            "spec_version": config.system.spec_version,
            "build_phase": config.system.build_phase,
        },
    )

    # 5. Health check.
    if not health_check(paths=paths, verbose=verbose):
        raise RuntimeError("System health check failed")

    if verbose:
        print("[OK] Bootstrap complete")
    return paths


def main() -> None:
    """CLI entry point for standalone health check: ``python -m src.runtime.bootstrap``."""
    import argparse

    parser = argparse.ArgumentParser(description="System bootstrap and health check")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run health check only (do not initialize logging)",
    )
    args = parser.parse_args()

    if args.check:
        # Health check mode: just validate, don't set up logging.
        try:
            paths = get_paths()
        except PathResolutionError as exc:
            print(f"❌ Path resolution failed: {exc}", file=sys.stderr)
            sys.exit(1)
        passed = health_check(paths=paths, verbose=True)
        sys.exit(0 if passed else 1)
    else:
        # Full bootstrap.
        try:
            bootstrap(verbose=True)
        except RuntimeError as exc:
            print(f"❌ Bootstrap failed: {exc}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()
