"""Backfill эмбеддингов для истории чата (S27-001).

Идемпотентно: берутся только сообщения с `embedding IS NULL`, поэтому повторный
запуск не пересчитывает уже обработанные. Батчи по `batch_size`, ограничение
`limit`, пауза между батчами (`sleep_s`) как простой rate-limit для провайдера.

Логика отделена от CLI (`scripts/backfill_embeddings.py`), чтобы её можно было
тестировать на фейковом провайдере без сети.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage
from app.services.llm.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)

#: Длина текста, отправляемого в эмбеддинг (защита от гигантских сообщений)
MAX_TEXT_CHARS = 4000


async def backfill_embeddings(
    db: AsyncSession,
    provider: EmbeddingProvider,
    *,
    batch_size: int = 50,
    limit: int | None = None,
    dry_run: bool = False,
    sleep_s: float = 0.0,
) -> dict[str, int]:
    """Заполнить `chat_messages.embedding` для сообщений без вектора.

    Возвращает статистику: `scanned`, `updated`, `skipped_empty`, `errors`,
    `remaining` (сколько осталось без эмбеддинга после запуска).
    """
    stats = {
        "scanned": 0,
        "updated": 0,
        "skipped_empty": 0,
        "errors": 0,
        "remaining": 0,
    }
    seen: set[UUID] = set()
    while True:
        query = select(ChatMessage).where(ChatMessage.embedding.is_(None))
        if seen:
            # dry-run и ошибки провайдера не пишут эмбеддинг: без исключения
            # уже обработанных сообщений цикл был бы бесконечным
            query = query.where(ChatMessage.id.notin_(seen))
        rows = (
            await db.execute(
                query.order_by(ChatMessage.created_at).limit(batch_size)
            )
        ).scalars().all()
        if not rows:
            break

        batch_processed = 0
        for message in rows:
            if limit is not None and stats["scanned"] >= limit:
                break
            stats["scanned"] += 1
            batch_processed += 1
            seen.add(message.id)
            text = (message.content or "").strip()
            if not text:
                stats["skipped_empty"] += 1
                continue
            try:
                vector = await provider.embed(text[:MAX_TEXT_CHARS])
            except Exception as exc:  # noqa: BLE001 — один сбой не рвёт backfill
                stats["errors"] += 1
                logger.warning(
                    "backfill_embed_failed",
                    message_id=str(message.id),
                    error=str(exc),
                )
                continue
            if not dry_run:
                message.embedding = vector
            stats["updated"] += 1

        if not dry_run and stats["updated"]:
            await db.commit()

        logger.info(
            "backfill_batch",
            processed=batch_processed,
            scanned=stats["scanned"],
            updated=stats["updated"],
            errors=stats["errors"],
        )

        if limit is not None and stats["scanned"] >= limit:
            break
        if batch_processed == 0:
            break
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)

    remaining = await count_without_embedding(db)
    stats["remaining"] = remaining
    logger.info("backfill_done", **stats)
    return stats


async def count_without_embedding(db: AsyncSession) -> int:
    """Сколько сообщений осталось без эмбеддинга"""
    from sqlalchemy import func

    total = await db.execute(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.embedding.is_(None))
    )
    return int(total.scalar_one())


def format_stats(stats: dict[str, Any]) -> str:
    """Человекочитаемая сводка для CLI"""
    return (
        f"scanned={stats.get('scanned', 0)} updated={stats.get('updated', 0)} "
        f"skipped_empty={stats.get('skipped_empty', 0)} errors={stats.get('errors', 0)} "
        f"remaining={stats.get('remaining', 0)}"
    )
