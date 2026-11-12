"""
Сервис оценок ответов ассистента (S43-003).

Ученик оценивает ответ ассистента (+1 / −1) и может оставить комментарий.
Оценки — источник сводки качества у администратора и вход для LLM-as-judge
(см. `docs/LLM_EVAL.md`).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, func, literal, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.chat import (
    ChatMessageRepository,
    ChatSessionRepository,
    MessageFeedbackRepository,
)
from app.errors import AccessDeniedError, NotFoundError, ValidationError
from app.models.chat import (
    ChatMessage,
    ChatSession,
    MessageFeedback,
    MessageRole,
)
from app.models.task import Task
from app.models.user import User
from app.services.cache import invalidate_quality_cache
from app.services.quality_queries import level_column, negative_contexts_cte

#: Сколько негативных оценок показывать в сводке
NEGATIVE_SAMPLES_LIMIT = 20

#: Сколько проблемных тем возвращать в сводке
TOP_PROBLEM_TOPICS_LIMIT = 10


def _provider_column() -> Any:
    """Колонка провайдера из метаданных ответа"""
    return ChatMessage.message_metadata["provider"].astext


def _model_column() -> Any:
    """Колонка модели из метаданных ответа"""
    return ChatMessage.message_metadata["model"].astext





class FeedbackService:
    """Оценки ответов: пользовательские операции и агрегаты для админа"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feedback = MessageFeedbackRepository(db)
        self.messages = ChatMessageRepository(db)
        self.sessions = ChatSessionRepository(db)

    async def _own_message(self, message_id: UUID, user: User) -> ChatMessage:
        """Ответ ассистента из сессии пользователя.

        Чужая сессия — 403, неизвестное сообщение — 404, вопрос ученика — 422.
        """
        message = await self.messages.get(message_id)
        if message is None:
            raise NotFoundError("Сообщение не найдено")
        session = await self.sessions.get(message.session_id)
        if session is None or session.user_id != user.id:
            raise AccessDeniedError("Нет доступа к этому сообщению")
        if message.role != MessageRole.ASSISTANT:
            raise ValidationError("Оценивать можно только ответ ассистента")
        return message

    async def set_feedback(
        self,
        message_id: UUID,
        user: User,
        value: int,
        comment: str | None = None,
    ) -> MessageFeedback:
        """Поставить или изменить оценку ответа"""
        if value not in (1, -1):
            raise ValidationError("Оценка может быть только 1 или -1")
        await self._own_message(message_id, user)
        feedback = await self.feedback.upsert(message_id, user.id, value, comment)
        await invalidate_quality_cache()
        return feedback

    async def remove_feedback(self, message_id: UUID, user: User) -> None:
        """Снять свою оценку ответа"""
        await self._own_message(message_id, user)
        await self.feedback.delete_for_user(message_id, user.id)
        await invalidate_quality_cache()

    async def list_for_session(
        self, session_id: UUID, user: User
    ) -> list[MessageFeedback]:
        """Мои оценки по сообщениям сессии"""
        session = await self.sessions.get(session_id)
        if session is None:
            raise NotFoundError("Сессия чата не найдена")
        if session.user_id != user.id:
            raise AccessDeniedError("Нет доступа к этой сессии")
        messages = await self.messages.get_session_messages(session_id)
        message_ids = [message.id for message in messages]
        return await self.feedback.list_for_messages(message_ids, user.id)

    async def quality_summary(self) -> dict[str, Any]:
        """Сводка качества ответов: счётчики, срезы и негативные оценки."""
        provider = _provider_column()
        model = _model_column()

        totals = (
            await self.db.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(MessageFeedback.value > 0).label("positive"),
                    func.count().filter(MessageFeedback.value < 0).label("negative"),
                ).select_from(MessageFeedback)
            )
        ).one()
        total = int(totals[0])
        positive = int(totals[1])
        negative = int(totals[2])

        rows = (
            await self.db.execute(
                select(
                    provider.label("provider"),
                    model.label("model"),
                    func.count().label("total"),
                    func.count().filter(MessageFeedback.value > 0).label("positive"),
                    func.count().filter(MessageFeedback.value < 0).label("negative"),
                )
                .select_from(MessageFeedback)
                .join(ChatMessage, ChatMessage.id == MessageFeedback.message_id)
                .group_by(provider, model)
            )
        ).all()

        by_provider: dict[str, dict[str, int]] = {}
        by_model: dict[str, dict[str, int]] = {}
        for row in rows:
            provider_name = str(row[0] or "unknown")
            model_name = str(row[1] or "unknown")
            counters = {"total": int(row[2]), "positive": int(row[3]), "negative": int(row[4])}
            for bucket, name in ((by_provider, provider_name), (by_model, model_name)):
                current = bucket.setdefault(
                    name, {"total": 0, "positive": 0, "negative": 0}
                )
                current["total"] += counters["total"]
                current["positive"] += counters["positive"]
                current["negative"] += counters["negative"]

        negatives = (
            await self.db.execute(
                select(
                    MessageFeedback.message_id,
                    MessageFeedback.comment,
                    MessageFeedback.created_at,
                    ChatMessage.content,
                    provider.label("provider"),
                    model.label("model"),
                )
                .select_from(MessageFeedback)
                .join(ChatMessage, ChatMessage.id == MessageFeedback.message_id)
                .where(MessageFeedback.value < 0)
                .order_by(MessageFeedback.created_at.desc())
                .limit(NEGATIVE_SAMPLES_LIMIT)
            )
        ).all()

        # S47-004: срез по уровню помощи. Уровень хранится в сессии, не в
        # метаданных сообщения; пустая строка у старых сессий — `unknown`.
        level = level_column()
        level_rows = (
            await self.db.execute(
                select(
                    level.label("level"),
                    func.count().label("total"),
                    func.count().filter(MessageFeedback.value > 0).label("positive"),
                    func.count().filter(MessageFeedback.value < 0).label("negative"),
                )
                .select_from(MessageFeedback)
                .join(ChatMessage, ChatMessage.id == MessageFeedback.message_id)
                .join(ChatSession, ChatSession.id == ChatMessage.session_id)
                .group_by(level)
                .order_by(func.count().desc(), level)
            )
        ).all()
        by_level = [
            _breakdown(
                str(row.level),
                {
                    "total": int(row.total),
                    "positive": int(row.positive),
                    "negative": int(row.negative),
                },
            )
            for row in level_rows
        ]

        # S47-004/D-003: негативные оценки по темам задач. Связка — только
        # через `message_metadata.task_context.task_id`; без контекста (или
        # если задача уже удалена) ответ попадает в группу «без задачи».
        negative_contexts = negative_contexts_cte()
        category_kind = case(
            (Task.id.is_(None), literal("none")),
            else_=literal("category"),
        )
        category_name = case(
            (Task.id.is_(None), literal("без задачи")),
            else_=Task.category,
        )
        category_query = (
            select(
                category_kind.label("kind"),
                category_name.label("name"),
                func.count().label("negative"),
            )
            .select_from(negative_contexts)
            .outerjoin(
                Task, Task.id.cast(String) == negative_contexts.c.task_id
            )
            .group_by(category_kind, category_name)
        )
        tag_values = (
            func.jsonb_array_elements_text(Task.tags)
            .table_valued("value")
            .alias("tag")
        )
        tag_query = (
            select(
                literal("tag").label("kind"),
                tag_values.c.value.label("name"),
                func.count().label("negative"),
            )
            .select_from(negative_contexts)
            .join(Task, Task.id.cast(String) == negative_contexts.c.task_id)
            .join(tag_values, true())
            .group_by(tag_values.c.value)
        )
        topics = category_query.union_all(tag_query).subquery("topics")
        topic_rows = (
            await self.db.execute(
                select(topics.c.kind, topics.c.name, topics.c.negative)
                .order_by(
                    topics.c.negative.desc(),
                    topics.c.kind,
                    topics.c.name,
                )
                .limit(TOP_PROBLEM_TOPICS_LIMIT)
            )
        ).all()

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "approval_rate": round(positive / total, 4) if total else 0.0,
            "by_provider": [
                _breakdown(name, counters) for name, counters in by_provider.items()
            ],
            "by_model": [
                _breakdown(name, counters) for name, counters in by_model.items()
            ],
            "by_level": by_level,
            "top_problem_topics": [
                {
                    "kind": str(row.kind),
                    "name": str(row.name),
                    "negative": int(row.negative),
                }
                for row in topic_rows
            ],
            "negative_samples": [
                {
                    "message_id": row[0],
                    "comment": row[1],
                    "content": row[3],
                    "provider": str(row[4] or "unknown"),
                    "model": str(row[5] or "unknown"),
                    "created_at": row[2],
                }
                for row in negatives
            ],
            "generated_at": datetime.now(UTC).isoformat(),
        }


def _breakdown(name: str, counters: dict[str, int]) -> dict[str, Any]:
    """Срез качества по одному имени с долей одобрения"""
    total = counters["total"]
    return {
        "name": name,
        "total": total,
        "positive": counters["positive"],
        "negative": counters["negative"],
        "approval_rate": round(counters["positive"] / total, 4) if total else 0.0,
    }
