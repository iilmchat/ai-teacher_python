"""Retention-политика (S26-003): удаление устаревших записей по срокам.

Логика живёт в `app` (а не в скрипте), чтобы её можно было тестировать и
переиспользовать; CLI — `backend/scripts/apply_retention.py`.

Сроки — `RETENTION_*_DAYS` (0 — таблица не обрабатывается). Удаление батчами,
каждый запуск пишет `retention_applied` с числом строк и обновляет
Prometheus-счётчики `retention_runs_total` / `retention_rows_deleted_total`
(KI-025).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import RETENTION_ROWS, RETENTION_RUNS
from app.db.database import async_session_factory
from app.models.audit import AuditLog
from app.models.chat import ChatMessage
from app.models.code import CodeExecution
from app.models.engagement import Notification
from app.models.task import TaskAttempt

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetentionTable:
    """Таблица, её модель, колонка времени и настройка дней"""

    name: str
    model: Any
    column: Any
    setting: str

    def cutoff(self) -> datetime | None:
        days = int(getattr(settings, self.setting) or 0)
        if days <= 0:
            return None
        return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


TABLES: tuple[RetentionTable, ...] = (
    RetentionTable(
        "chat_messages", ChatMessage, ChatMessage.created_at, "retention_chat_messages_days"
    ),
    RetentionTable(
        "code_executions",
        CodeExecution,
        CodeExecution.created_at,
        "retention_code_executions_days",
    ),
    RetentionTable(
        "notifications",
        Notification,
        Notification.created_at,
        "retention_notifications_days",
    ),
    RetentionTable(
        "audit_log", AuditLog, AuditLog.created_at, "retention_audit_log_days"
    ),
    RetentionTable(
        "task_attempts",
        TaskAttempt,
        TaskAttempt.created_at,
        "retention_task_attempts_days",
    ),
)


async def _count(db: AsyncSession, table: RetentionTable, cutoff: datetime) -> int:
    total = await db.execute(
        select(func.count()).select_from(table.model).where(table.column < cutoff)
    )
    return int(total.scalar_one())


async def _delete_batch(
    db: AsyncSession, table: RetentionTable, cutoff: datetime, batch_size: int
) -> int:
    ids = (
        await db.execute(
            select(table.model.id).where(table.column < cutoff).limit(batch_size)
        )
    ).scalars().all()
    if not ids:
        return 0
    await db.execute(delete(table.model).where(table.model.id.in_(ids)))
    await db.commit()
    return len(ids)


async def apply_retention(
    *, dry_run: bool, only: str | None, batch_size: int
) -> dict[str, int]:
    """Применить retention; возвращает число удалённых (или подлежащих) строк"""
    results: dict[str, int] = {}
    async with async_session_factory() as db:
        for table in TABLES:
            if only and table.name != only:
                continue
            cutoff = table.cutoff()
            if cutoff is None:
                results[table.name] = 0
                RETENTION_RUNS.labels(table.name, "disabled").inc()
                logger.info("retention_skipped", table=table.name, reason="disabled")
                continue

            candidates = await _count(db, table, cutoff)
            if dry_run:
                results[table.name] = candidates
                RETENTION_RUNS.labels(table.name, "dry_run").inc()
                logger.info(
                    "retention_dry_run",
                    table=table.name,
                    cutoff=cutoff.isoformat(),
                    rows=candidates,
                )
                continue

            deleted = 0
            while True:
                chunk = await _delete_batch(db, table, cutoff, batch_size)
                if chunk == 0:
                    break
                deleted += chunk
            results[table.name] = deleted
            RETENTION_ROWS.labels(table.name).inc(deleted)
            RETENTION_RUNS.labels(table.name, "applied").inc()
            logger.info(
                "retention_applied",
                table=table.name,
                cutoff=cutoff.isoformat(),
                deleted=deleted,
            )
    return results


__all__ = ["TABLES", "RetentionTable", "apply_retention"]
