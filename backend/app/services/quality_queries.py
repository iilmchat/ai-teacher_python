"""Общие SQL-выражения сводки качества LLM (S47-004).

`task_context` хранится в метаданных **вопроса ученика** (S42-006), а оценка
привязана к ответу ассистента. Поэтому контекст задачи ищется в ближайшем
предыдущем сообщении ученика той же сессии — это работает и для старых
оценок, у которых в метаданных ответа контекста нет.
"""

from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import aliased

from app.models.chat import ChatMessage, ChatSession, MessageFeedback, MessageRole


def level_column() -> Any:
    """Уровень помощи из сессии; пустой/пробельный — `unknown`."""
    return func.coalesce(
        func.nullif(func.lower(func.trim(ChatSession.level)), ""),
        "unknown",
    )


def negative_contexts_cte() -> Any:
    """CTE негативных оценок с `task_id` из контекста вопроса.

    Для каждой негативной оценки берётся ответ ассистента и ближайший
    предыдущий вопрос ученика в той же сессии. Если вопроса/контекста нет,
    `task_id` остаётся NULL — в сводке это группа «без задачи» (D-003).
    """
    assistant = aliased(ChatMessage, name="feedback_message")
    previous_user = aliased(ChatMessage, name="previous_user")
    previous_task = (
        select(
            previous_user.message_metadata["task_context"]["task_id"]
            .astext.label("task_id")
        )
        .where(
            previous_user.session_id == assistant.session_id,
            previous_user.role == MessageRole.USER,
            previous_user.created_at <= assistant.created_at,
        )
        .order_by(
            previous_user.created_at.desc(),
            previous_user.id.desc(),
        )
        .limit(1)
        .lateral("previous_task")
    )
    return (
        select(
            assistant.id.label("message_id"),
            previous_task.c.task_id.label("task_id"),
        )
        .select_from(MessageFeedback)
        .join(assistant, assistant.id == MessageFeedback.message_id)
        .outerjoin(previous_task, true())
        .where(MessageFeedback.value < 0)
        .cte("negative_contexts")
    )
