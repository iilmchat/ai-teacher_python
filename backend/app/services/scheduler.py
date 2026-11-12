"""Встроенный планировщик retention (KI-025).

Retention по умолчанию применяется вручную или по cron
(`scripts/apply_retention.py`). Если включён `RETENTION_SCHEDULER_ENABLED`,
приложение само раз в сутки применяет `RETENTION_*_DAYS` — cron становится
опциональным.

Планировщик — одна asyncio-задача в процессе API:

* время запуска — `RETENTION_SCHEDULER_AT` (``HH:MM`` UTC, по умолчанию 03:30);
* на время прогона берётся advisory-lock PostgreSQL: при нескольких
  инстансах/воркерах retention не выполнится дважды;
* остановка — через :class:`asyncio.Event`: текущий прогон доигрывается,
  новый не начинается.

В логах — события ``retention_scheduler_*``; число удалённых строк уходит в
Prometheus (`retention_rows_deleted_total`).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import scheduler_success_observed
from app.db.database import async_session_factory
from app.services.retention import apply_retention

logger = structlog.get_logger(__name__)

#: Ключ PostgreSQL advisory-lock (bigint). Фиксированный: разные инстансы
#: приложения конкурируют за один и тот же лок.
ADVISORY_LOCK_KEY = 0x41495452  # ASCII "AITR"

#: Время запуска, если `RETENTION_SCHEDULER_AT` не разобрать.
FALLBACK_RUN_AT = time(3, 30)
#: Размер батча удаления по умолчанию (как у CLI `--batch-size`).
DEFAULT_BATCH_SIZE = 1000
#: Сколько ждать завершения текущего прогона при остановке приложения.
SHUTDOWN_TIMEOUT_S = 30.0


@dataclass(slots=True)
class SchedulerHandle:
    """Запущенный планировщик: задача и сигнал остановки."""

    task: asyncio.Task[None]
    stop: asyncio.Event = field(default_factory=asyncio.Event)


def parse_run_at(value: str) -> time:
    """Разобрать ``HH:MM`` (UTC); при ошибке — предупреждение и 03:30."""
    raw = (value or "").strip()
    try:
        hours, minutes = raw.split(":", maxsplit=1)
        return time(int(hours), int(minutes))
    except ValueError:
        logger.warning(
            "retention_scheduler_bad_time", value=raw, fallback=FALLBACK_RUN_AT.strftime("%H:%M")
        )
        return FALLBACK_RUN_AT


def seconds_until_next_run(now: datetime, run_at: time) -> float:
    """Секунды до следующего ``run_at`` (UTC); ровно в момент запуска — сутки."""
    candidate = datetime.combine(now.date(), run_at, tzinfo=UTC)
    if candidate <= now:
        candidate += timedelta(days=1)
    return max((candidate - now).total_seconds(), 0.0)


async def _acquire_lock(session: AsyncSession) -> bool:
    """Взять advisory-lock на время прогона (False — занят другим инстансом)"""
    result = await session.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
    )
    return bool(result.scalar())


async def _release_lock(session: AsyncSession) -> None:
    """Отпустить advisory-lock (всегда, даже если прогон упал)"""
    await session.execute(
        text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
    )


async def run_retention_once(
    *, batch_size: int = DEFAULT_BATCH_SIZE
) -> dict[str, int] | None:
    """Один прогон retention под advisory-lock.

    Возвращает число удалённых строк по таблицам; ``None`` — лок занят
    другим инстансом, прогон пропущен.
    """
    async with async_session_factory() as session:
        if not await _acquire_lock(session):
            logger.info("retention_scheduler_skipped", reason="lock_held")
            return None
        try:
            results = await apply_retention(
                dry_run=False, only=None, batch_size=max(1, batch_size)
            )
            logger.info("retention_scheduler_applied", deleted=results)
            # S35-003: алерт RetentionStale смотрит на этот timestamp.
            scheduler_success_observed(
                job="retention", timestamp=datetime.now(UTC).timestamp()
            )
            return results
        finally:
            await _release_lock(session)


async def scheduler_loop(
    *, stop: asyncio.Event, batch_size: int = DEFAULT_BATCH_SIZE
) -> None:
    """Ждать очередного времени запуска и применять retention, пока нет ``stop``"""
    run_at = parse_run_at(settings.retention_scheduler_at)
    while not stop.is_set():
        delay = seconds_until_next_run(datetime.now(UTC), run_at)
        logger.info("retention_scheduler_wait", seconds=round(delay))
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass
        else:
            return
        try:
            await run_retention_once(batch_size=batch_size)
        except Exception as exc:  # noqa: BLE001 — планировщик не должен падать
            logger.error("retention_scheduler_failed", error=str(exc))
    logger.info("retention_scheduler_stopped")


def start_scheduler(*, batch_size: int = DEFAULT_BATCH_SIZE) -> SchedulerHandle:
    """Создать фоновую задачу планировщика (вызывается из lifespan)"""
    stop = asyncio.Event()
    task = asyncio.create_task(
        scheduler_loop(stop=stop, batch_size=batch_size), name="retention-scheduler"
    )
    handle = SchedulerHandle(task=task, stop=stop)
    logger.info("retention_scheduler_started", at=settings.retention_scheduler_at)
    return handle


async def stop_scheduler(handle: SchedulerHandle | None) -> None:
    """Остановить планировщик, дав доиграть текущий прогон"""
    if handle is None:
        return
    handle.stop.set()
    try:
        await asyncio.wait_for(
            asyncio.shield(handle.task), timeout=SHUTDOWN_TIMEOUT_S
        )
    except TimeoutError:
        logger.warning("retention_scheduler_shutdown_timeout", timeout=SHUTDOWN_TIMEOUT_S)
        handle.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await handle.task


__all__ = [
    "ADVISORY_LOCK_KEY",
    "DEFAULT_BATCH_SIZE",
    "FALLBACK_RUN_AT",
    "SchedulerHandle",
    "parse_run_at",
    "run_retention_once",
    "scheduler_loop",
    "seconds_until_next_run",
    "start_scheduler",
    "stop_scheduler",
]
