"""Structured logging setup.

Wires structlog so:
- In ``ENVIRONMENT=production``/``staging`` we emit single-line JSON that
  Cloud Logging ingests with structured fields (severity, message, plus any
  bound context like ``request_id``, ``tenant_id``).
- In local/test/development we render colourised key=value output with
  timestamps for human readability.

A small middleware (in ``backend.main``) binds ``request_id`` per request via
``structlog.contextvars`` so every log line within a request shares it.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from backend.config import Settings, get_settings


# Map structlog level names to the keys Google Cloud Logging expects.
def _gcp_severity(_logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Translate structlog's ``level`` field to GCP's ``severity`` field."""
    level = event_dict.pop("level", method_name).upper()
    # Cloud Logging severity levels: DEFAULT, DEBUG, INFO, NOTICE, WARNING,
    # ERROR, CRITICAL, ALERT, EMERGENCY.
    if level == "WARN":
        level = "WARNING"
    event_dict["severity"] = level
    return event_dict


def _rename_event_to_message(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Cloud Logging's structured payload uses ``message`` rather than ``event``."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def configure_logging(settings: Settings | None = None) -> None:
    """Idempotent setup. Call once at startup."""
    if settings is None:
        settings = get_settings()

    is_prod = settings.environment in ("production", "staging")

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if is_prod:
        renderer_chain: list[Processor] = [
            _gcp_severity,
            _rename_event_to_message,
            structlog.processors.JSONRenderer(),
        ]
    else:
        renderer_chain = [
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ]

    # structlog → stdlib bridge: structlog loggers run shared_processors then
    # hand off to ProcessorFormatter, which runs renderer_chain. stdlib
    # records (uvicorn, etc.) are run through foreign_pre_chain first so
    # they end up with the same fields before the renderer.
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *renderer_chain,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    # Tame the noisy access logger; uvicorn already emits one access record
    # per request, no need for httpx/uvicorn debug spam in prod.
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Drop-in replacement for ``logging.getLogger(__name__)``."""
    return structlog.stdlib.get_logger(name)
