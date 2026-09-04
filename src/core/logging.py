"""Structured logging system.

Specification anchors:
  * BUILD_PLAN.md §1 — logging is a Phase 1 foundation component.
  * SYSTEM_RULES.md §B.15 — "Log meaningful state transitions and external calls."

By default logs are written in JSON format for machine processing while also
being printed to the console in a human-readable text format for developers.
Every log record includes the component name and process context so that parallel
research tasks or multiple agent invocations remain distinguishable.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping

from src.core.config import LoggingSection, SystemConfig, get_config
from src.core.paths import SystemPaths, get_paths

__all__ = [
    "SYSTEM_LOGGER_NAME",
    "setup_logging",
    "get_logger",
    "reset_logging",
]

SYSTEM_LOGGER_NAME = "autonomi"

_LOGGING_SETUP_COMPLETED = False


class _JSONFormatter(logging.Formatter):
    """JSON lines formatter for machine-processable logs."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Attach any extra context injected by logger.bind(...) or structlog-style usage
        extra_keys = {
            key
            for key in vars(record)
            if key
            not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            }
        }
        if extra_keys:
            payload["context"] = {key: getattr(record, key) for key in extra_keys}
        return json.dumps(payload, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    """Human-friendly console formatter."""

    def format(self, record: logging.LogRecord) -> str:
        # Include component name so developers know which subsystem emitted the log
        short_name = record.name.replace(SYSTEM_LOGGER_NAME + ".", "")
        record.component = short_name  # type: ignore[attr-defined]
        return super().format(record)


def setup_logging(
    *,
    config: SystemConfig | None = None,
    paths: SystemPaths | None = None,
    force: bool = False,
) -> None:
    """Initialize the logging system per the loaded configuration.

    This function is idempotent by default: repeated calls do nothing unless
    ``force=True`` is specified (used by tests that reconfigure mid-run).

    Parameters
    ----------
    config:
        System configuration; defaults to :func:`get_config`.
    paths:
        System paths; defaults to :func:`get_paths`.
    force:
        When ``True``, tear down and rebuild the logging system.
    """
    global _LOGGING_SETUP_COMPLETED

    if _LOGGING_SETUP_COMPLETED and not force:
        return

    resolved_config = config or get_config()
    resolved_paths = paths or get_paths()
    log_cfg: LoggingSection = resolved_config.logging

    # Ensure logs directory exists (may not exist on first run)
    resolved_paths.logs_dir.mkdir(parents=True, exist_ok=True)

    # Reset the root of the system logger tree
    root_logger = logging.getLogger(SYSTEM_LOGGER_NAME)
    root_logger.handlers.clear()
    root_logger.setLevel(log_cfg.level)
    root_logger.propagate = False

    handlers: list[logging.Handler] = []

    if log_cfg.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_cfg.level)
        # Console uses text format for readability
        console_formatter = _TextFormatter(
            fmt="%(asctime)s [%(levelname)s] %(component)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)

    if log_cfg.file:
        log_file_path = resolved_paths.logs_dir / log_cfg.filename
        file_handler = RotatingFileHandler(
            str(log_file_path),
            maxBytes=log_cfg.max_bytes,
            backupCount=log_cfg.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_cfg.level)
        # File uses JSON for machine processing
        if log_cfg.format == "json":
            file_formatter = _JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        else:
            file_formatter = _TextFormatter(
                fmt="%(asctime)s [%(levelname)s] %(component)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    _LOGGING_SETUP_COMPLETED = True

    # Emit a sentinel record confirming the system booted
    root_logger.info(
        "Logging initialized",
        extra={
            "spec_version": resolved_config.system.spec_version,
            "build_phase": resolved_config.system.build_phase,
        },
    )


@lru_cache(maxsize=None)
def get_logger(name: str) -> logging.Logger:
    """Return a logger for the specified component.

    All component loggers are children of ``"autonomi"`` so that a single call
    to :func:`setup_logging` configures everything.

    Examples
    --------
    >>> from src.core.logging import get_logger
    >>> logger = get_logger(__name__)
    >>> logger.info("Starting discovery", extra={"query": "machine learning"})
    """
    if not name.startswith(SYSTEM_LOGGER_NAME + "."):
        qualified = f"{SYSTEM_LOGGER_NAME}.{name}"
    else:
        qualified = name
    return logging.getLogger(qualified)


def reset_logging() -> None:
    """Clear cached loggers and force reconfiguration on next :func:`setup_logging`.

    Used by tests that modify the logging config mid-run.
    """
    global _LOGGING_SETUP_COMPLETED
    _LOGGING_SETUP_COMPLETED = False
    get_logger.cache_clear()
    root_logger = logging.getLogger(SYSTEM_LOGGER_NAME)
    root_logger.handlers.clear()
