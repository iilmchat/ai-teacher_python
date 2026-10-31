"""Настройка structlog (S25-001).

Единая точка конфигурации: JSON-логи в production/CI, человекочитаемые — в
development (`LOG_FORMAT=console`). `merge_contextvars` обязателен: без него
`request_id`, привязанный middleware, не попадёт в записи логов.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config import settings

_configured = False


def configure_logging() -> None:
    """Идемпотентная настройка логирования (вызывается при импорте app.main)"""
    global _configured
    if _configured:
        return
    _configured = True

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=sys.stdout.isatty()
        )
    else:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # uvicorn/сторонние логгеры — через stdlib, чтобы формат был единым
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout)


def reset_logging() -> None:
    """Сбросить флаг (тесты)"""
    global _configured
    _configured = False
