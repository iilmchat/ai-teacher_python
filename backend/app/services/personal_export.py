"""Экспорт собственных данных пользователя — GET /users/me/export (S45-003).

Персональные данные (PRIVACY.md, право на переносимость): профиль, прогресс
по задачам и попытки, комментарии учителей к попыткам, сессии чата с
сообщениями, собственные оценки ответов ассистента, уведомления, достижения.

Правила:

* выгружаются данные **только** этого пользователя, чужих нет;
* служебные поля не выгружаются: `embedding` сообщений (вектор, а не «данные
  пользователя») и внутренние ключи; в `message_metadata` остаётся то, что
  пользователь видел сам (провайдер/модель ответа);
* даты — ISO 8601, роли и статусы — строковые значения из enum;
* формат — один JSON-документ; при больших объёмах это приемлемо, т.к.
  отдельного пользователя обычно ограничивают лимиты чата и попыток.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageFeedback
from app.models.engagement import Notification, UserAchievement
from app.models.task import (
    AttemptFeedback,
    TaskAttempt,
    UserTaskProgress,
)
from app.models.user import User


def _iso(value: datetime | None) -> str | None:
    """Дата в ISO 8601 (None остаётся None)"""
    return value.isoformat() if value is not None else None


def _to_str(value: Any) -> Any:
    """Значения enum и UUID сериализуются строками, остальное как есть"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, list):
        return [_to_str(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_str(item) for key, item in value.items()}
    return getattr(value, "value", str(value))


def _serialize_message(message: ChatMessage) -> dict[str, Any]:
    """Сообщение чата без `embedding` (вектор — внутренние данные поиска)"""
    return {
        "id": str(message.id),
        "session_id": str(message.session_id),
        "role": message.role.value,
        "content": message.content,
        "code_blocks": _to_str(message.code_blocks),
        "metadata": _to_str(message.message_metadata),
        "created_at": _iso(message.created_at),
    }


def _serialize_session(session: ChatSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "level": session.level,
        "title": session.title,
        "pinned": session.pinned,
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
        "messages": [],
    }


def _serialize_progress(row: UserTaskProgress) -> dict[str, Any]:
    return {
        "task_id": str(row.task_id),
        "status": row.status.value,
        "attempts": row.attempts,
        "best_solution": row.best_solution,
        "draft_code": row.draft_code,
        "draft_updated_at": _iso(row.draft_updated_at),
        "completed_at": _iso(row.completed_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_attempt(row: TaskAttempt) -> dict[str, Any]:
    return {
        "task_id": str(row.task_id),
        "code": row.code,
        "passed": row.passed,
        "passed_count": row.passed_count,
        "total_count": row.total_count,
        "created_at": _iso(row.created_at),
    }


def _serialize_notification(row: Notification) -> dict[str, Any]:
    return {
        "type": row.type,
        "payload": _to_str(row.payload),
        "read_at": _iso(row.read_at),
        "created_at": _iso(row.created_at),
    }


def _serialize_achievement(row: UserAchievement) -> dict[str, Any]:
    return {
        "code": row.code,
        "earned_at": _iso(row.earned_at),
    }


def _serialize_feedback(
    row: AttemptFeedback, teacher_name: str
) -> dict[str, Any]:
    """Комментарий учителя к попытке — ученик видел его в истории (S46-002)"""
    return {
        "attempt_id": str(row.attempt_id),
        "comment": row.comment,
        "teacher_name": teacher_name,
        "created_at": _iso(row.created_at),
    }


def _serialize_message_feedback(row: MessageFeedback) -> dict[str, Any]:
    """Собственная оценка ответа ассистента (S43-003)"""
    return {
        "message_id": str(row.message_id),
        "value": row.value,
        "comment": row.comment,
        "created_at": _iso(row.created_at),
    }


def _serialize_profile(user: User) -> dict[str, Any]:
    """Профиль: то, что пользователь видит на странице настроек"""
    return {
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "level": user.level.value,
        "settings": _to_str(user.settings),
        "created_at": _iso(user.created_at),
        "last_active": _iso(user.last_active),
    }


async def collect_user_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """Собрать JSON со всеми данными пользователя (только его)"""
    user_id = user.id

    sessions = (
        (
            await db.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.created_at)
            )
        )
        .scalars()
        .all()
    )
    # Сообщения собираем одним запросом по сессиям пользователя и
    # группируем по сессии; выбираем колонки без `embedding`.
    session_ids = [session.id for session in sessions]
    messages_by_session: dict[UUID, list[dict[str, Any]]] = {}
    if session_ids:
        messages = (
            (
                await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id.in_(session_ids))
                    .order_by(ChatMessage.created_at)
                )
            )
            .scalars()
            .all()
        )
        for message in messages:
            messages_by_session.setdefault(message.session_id, []).append(
                _serialize_message(message)
            )

    session_items = [_serialize_session(session) for session in sessions]
    for item in session_items:
        item["messages"] = messages_by_session.get(UUID(item["id"]), [])

    progress = (
        (
            await db.execute(
                select(UserTaskProgress)
                .where(UserTaskProgress.user_id == user_id)
                .order_by(UserTaskProgress.updated_at)
            )
        )
        .scalars()
        .all()
    )
    attempts = (
        (
            await db.execute(
                select(TaskAttempt)
                .where(TaskAttempt.user_id == user_id)
                .order_by(TaskAttempt.created_at)
            )
        )
        .scalars()
        .all()
    )
    notifications = (
        (
            await db.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at)
            )
        )
        .scalars()
        .all()
    )
    achievements = (
        (
            await db.execute(
                select(UserAchievement)
                .where(UserAchievement.user_id == user_id)
                .order_by(UserAchievement.earned_at)
            )
        )
        .scalars()
        .all()
    )
    message_feedback = (
        (
            await db.execute(
                select(MessageFeedback)
                .where(MessageFeedback.user_id == user_id)
                .order_by(MessageFeedback.created_at)
            )
        )
        .scalars()
        .all()
    )
    attempt_ids = [attempt.id for attempt in attempts]
    feedback_rows: list[tuple[AttemptFeedback, str]] = []
    if attempt_ids:
        feedback_result = await db.execute(
            select(AttemptFeedback, User.username)
            .join(User, User.id == AttemptFeedback.teacher_id)
            .where(AttemptFeedback.attempt_id.in_(attempt_ids))
            .order_by(AttemptFeedback.created_at)
        )
        feedback_rows = []
        for feedback, teacher_name in feedback_result.all():
            feedback_rows.append((feedback, teacher_name))

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "profile": _serialize_profile(user),
        "task_progress": [_serialize_progress(row) for row in progress],
        "task_attempts": [_serialize_attempt(row) for row in attempts],
        "teacher_feedback": [
            _serialize_feedback(feedback, teacher_name)
            for feedback, teacher_name in feedback_rows
        ],
        "chat_sessions": session_items,
        "message_feedback": [
            _serialize_message_feedback(row) for row in message_feedback
        ],
        "notifications": [_serialize_notification(row) for row in notifications],
        "achievements": [_serialize_achievement(row) for row in achievements],
    }


def export_filename(prefix: str = "ai-teacher-export") -> str:
    """Имя файла для Content-Disposition (дата-время UTC)"""
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}.json"
