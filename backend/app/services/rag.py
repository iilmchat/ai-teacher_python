"""
RAG-lite: семантический поиск по истории чата (S19-005).

Поиск всегда ограничен **своими** сессиями: запросы фильтруются по
`chat_sessions.user_id`, поэтому чужое сообщение не может попасть в выдачу.

Два режима:
- **semantic** — если `RAG_ENABLED=true`, провайдер эмбеддингов доступен и в
  базе есть векторы; ранжирование по косинусному расстоянию (pgvector HNSW);
- **ilike** — всегда доступный fallback (подстрока без учёта регистра). Он же
  используется, если провайдер недоступен, упал или семантическая выдача пуста.

Эмбеддинги для новых сообщений считаются **best-effort**: ошибка провайдера
логируется, сообщение всё равно сохраняется и отправляется (fail-open).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.chat import ChatMessageRepository
from app.errors import ValidationError
from app.models.chat import ChatMessage
from app.services.llm.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)

#: Режимы выдачи
SearchMode = Literal["semantic", "ilike"]


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Найденное сообщение и (для semantic) косинусная близость"""

    message: ChatMessage
    score: float | None = None


async def try_embed(
    provider: EmbeddingProvider | None, text: str
) -> list[float] | None:
    """Best-effort эмбеддинг: ``None`` при выключенном RAG или любой ошибке"""
    if not settings.rag_enabled or provider is None:
        return None
    try:
        vector = await provider.embed(text)
    except Exception as exc:  # noqa: BLE001 — RAG не должен ломать чат
        logger.warning("embedding_failed", error=str(exc))
        return None

    if len(vector) != settings.rag_embedding_dim:
        logger.warning(
            "embedding_dim_mismatch",
            expected=settings.rag_embedding_dim,
            actual=len(vector),
        )
        return None
    return vector


async def search_chat_messages(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    limit: int,
    provider: EmbeddingProvider | None,
) -> tuple[SearchMode, list[SearchHit]]:
    """Найти сообщения пользователя по строке/смыслу.

    Возвращает режим выдачи и найденные сообщения; чужие сессии исключены
    на уровне SQL.
    """
    text = query.strip()
    if not text:
        raise ValidationError("Поисковый запрос не может быть пустым")

    repository = ChatMessageRepository(db)

    if settings.rag_enabled and provider is not None:
        vector = await try_embed(provider, text)
        if vector is not None:
            semantic_rows = await repository.search_user_messages_semantic(
                user_id, vector, limit
            )
            if semantic_rows:
                logger.info(
                    "rag_search",
                    mode="semantic",
                    results=len(semantic_rows),
                    user_id=str(user_id),
                )
                return "semantic", [
                    SearchHit(message=message, score=score)
                    for message, score in semantic_rows
                ]
            logger.info(
                "rag_search_empty_semantic",
                user_id=str(user_id),
                fallback="ilike",
            )

    messages = await repository.search_user_messages_ilike(user_id, text, limit)
    logger.info(
        "rag_search", mode="ilike", results=len(messages), user_id=str(user_id)
    )
    return "ilike", [SearchHit(message=message) for message in messages]
