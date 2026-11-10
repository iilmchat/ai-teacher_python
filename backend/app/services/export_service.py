"""Экспорт аналитики (S26-001).

CSV или JSON, потоково (серверный курсор SQLAlchemy), с лимитом строк:
`EXPORT_MAX_ROWS` (по умолчанию 100 000). Лимит защищает процесс API и БД от
выгрузки «всего на свете»; при обрезке ответ получает заголовок
`X-Export-Truncated: true`, а аудит фиксирует фактическое число строк.

Наборы данных (`dataset`):

* `users` — id, username, email, role, level, created_at, last_active;
* `tasks` — id, title, difficulty, category, is_active, created_at;
* `attempts` — прогресс учеников по задачам (status, attempts, completed_at);
* `activity` — сообщения чата и запуски кода (тип, время, краткая сводка);
* `negative_feedback` — негативные оценки ответов с уровнем и задачей
  (S47-004/D-008).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import String, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageFeedback
from app.models.code import CodeExecution
from app.models.task import Task, UserTaskProgress
from app.models.user import User
from app.services.quality_queries import level_column, negative_contexts_cte

#: Допустимые наборы и заголовки CSV
DATASETS: dict[str, list[str]] = {
    "users": ["id", "username", "email", "role", "level", "created_at", "last_active"],
    "tasks": ["id", "title", "difficulty", "category", "is_active", "created_at"],
    "attempts": [
        "user_id",
        "task_id",
        "status",
        "attempts",
        "completed_at",
        "updated_at",
    ],
    "activity": ["kind", "id", "user_id", "created_at", "summary"],
    # S47-004/D-008: негативные оценки ответов ассистента
    "negative_feedback": [
        "message_id",
        "comment",
        "provider",
        "model",
        "level",
        "task_id",
        "created_at",
    ],
}


def _build_query(dataset: str) -> Any:
    if dataset == "users":
        return select(
            User.id,
            User.username,
            User.email,
            User.role,
            User.level,
            User.created_at,
            User.last_active,
        ).order_by(User.created_at)
    if dataset == "tasks":
        return select(
            Task.id,
            Task.title,
            Task.difficulty,
            Task.category,
            Task.is_active,
            Task.created_at,
        ).order_by(Task.created_at)
    if dataset == "attempts":
        return select(
            UserTaskProgress.user_id,
            UserTaskProgress.task_id,
            UserTaskProgress.status,
            UserTaskProgress.attempts,
            UserTaskProgress.completed_at,
            UserTaskProgress.updated_at,
        ).order_by(UserTaskProgress.updated_at)
    if dataset == "activity":
        # Объединяем два источника в один поток «активности»; у сообщения
        # пользователь берётся из сессии чата (у самого сообщения его нет).
        messages = select(
            ChatMessage.created_at.label("created_at"),
            ChatSession.user_id.label("user_id"),
            ChatMessage.id.label("id"),
            ChatMessage.role.cast(str).label("kind"),
            ChatMessage.content.label("summary"),
        ).join(ChatSession, ChatSession.id == ChatMessage.session_id)
        executions = select(
            CodeExecution.created_at.label("created_at"),
            CodeExecution.user_id.label("user_id"),
            CodeExecution.id.label("id"),
            CodeExecution.success.cast(str).label("kind"),
            CodeExecution.code.label("summary"),
        )
        return messages.union_all(executions).order_by("created_at")
    if dataset == "negative_feedback":
        negative_contexts = negative_contexts_cte()
        task_id = case(
            (Task.id.is_(None), "без задачи"),
            else_=Task.id.cast(String),
        )
        return (
            select(
                negative_contexts.c.message_id.label("message_id"),
                MessageFeedback.comment.label("comment"),
                func.coalesce(
                    ChatMessage.message_metadata["provider"].astext, "unknown"
                ).label("provider"),
                func.coalesce(
                    ChatMessage.message_metadata["model"].astext, "unknown"
                ).label("model"),
                level_column().label("level"),
                task_id.label("task_id"),
                MessageFeedback.created_at.label("created_at"),
            )
            .select_from(negative_contexts)
            .join(
                MessageFeedback,
                MessageFeedback.message_id == negative_contexts.c.message_id,
            )
            .join(ChatMessage, ChatMessage.id == negative_contexts.c.message_id)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .outerjoin(
                Task, Task.id.cast(String) == negative_contexts.c.task_id
            )
            .order_by(MessageFeedback.created_at)
        )
    raise ValueError(f"Неизвестный набор данных: {dataset}")


def _serialize(row: Any, columns: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in columns:
        value = getattr(row, column, None)
        if value is None:
            data[column] = None
        elif hasattr(value, "isoformat"):
            data[column] = value.isoformat()
        elif hasattr(value, "value"):  # enum
            data[column] = value.value
        else:
            data[column] = value
    return data


async def iter_rows(
    db: AsyncSession, dataset: str, *, limit: int
) -> AsyncIterator[dict[str, Any]]:
    """Поток строк набора (без загрузки всей таблицы в память)"""
    columns = DATASETS[dataset]
    result = await db.stream(_build_query(dataset))
    count = 0
    async for row in result:
        if limit and count >= limit:
            break
        count += 1
        yield _serialize(row, columns)


async def stream_csv(
    db: AsyncSession, dataset: str, *, limit: int
) -> AsyncIterator[bytes]:
    """CSV-поток с заголовком"""
    columns = DATASETS[dataset]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    yield buffer.getvalue().encode("utf-8")

    async for row in iter_rows(db, dataset, limit=limit):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writerow(row)
        yield buffer.getvalue().encode("utf-8")


async def stream_json(
    db: AsyncSession, dataset: str, *, limit: int
) -> AsyncIterator[bytes]:
    """JSON-массив, отдаваемый по частям (валидный JSON для больших выгрузок)"""
    yield b'{"dataset":"' + dataset.encode() + b'","items":['
    first = True
    async for row in iter_rows(db, dataset, limit=limit):
        chunk = json.dumps(row, ensure_ascii=False, default=str)
        yield (b"" if first else b",") + chunk.encode("utf-8")
        first = False
    yield b"]}\n"
