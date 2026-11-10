"""
Тесты сводки качества LLM и выгрузки негативных оценок (S47-004).

Сводка: срез по уровню помощи из `chat_sessions.level`, топ проблемных
категорий/тегов задач через `message_metadata.task_context.task_id` и группа
«без задачи» (D-003). Экспорт: потоково, с лимитом `EXPORT_MAX_ROWS` и
аудитом `quality.exported` (D-008).
"""

import csv
import io
import json
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.user import UserRepository
from app.models.audit import AuditLog
from app.models.chat import ChatSession
from app.models.task import Task, TaskDifficulty
from app.models.user import UserRole
from tests.fake_llm import FakeProvider, install_fake_provider, uninstall_fake_provider

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
QUALITY_URL = "/api/v1/admin/quality"
EXPORT_URL = "/api/v1/admin/quality/export"


@pytest.fixture
def fake_provider() -> FakeProvider:
    provider = FakeProvider()
    install_fake_provider(provider)
    yield provider
    uninstall_fake_provider()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(client: AsyncClient, username: str) -> str:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
    )
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    token: str = response.json()["access_token"]
    return token


async def _admin_token(
    client: AsyncClient, db: AsyncSession, username: str = "quality_admin"
) -> str:
    token = await _register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


async def _make_task(
    db: AsyncSession,
    *,
    title: str,
    category: str,
    tags: list[str],
) -> Task:
    task = Task(
        title=title,
        description=f"Условие задачи «{title}».",
        difficulty=TaskDifficulty.EASY,
        category=category,
        tags=tags,
        test_cases=[{"input": "1\n", "expected_output": "1"}],
        hints=[],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _answer(
    client: AsyncClient,
    token: str,
    db: AsyncSession,
    *,
    level: str | None = None,
    task_id: UUID | None = None,
) -> str:
    """Создать ответ ассистента; вернуть id ответа."""
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    payload: dict[str, Any] = {"content": "Объясни задачу"}
    if task_id is not None:
        payload["task_id"] = str(task_id)
    sent = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json=payload,
        headers=_auth(token),
    )
    assert sent.status_code == 201, sent.text
    # Уровень меняем после сообщения: чат валидирует его при отправке, а для
    # среза качества важно итоговое значение в сессии (включая пустое).
    if level is not None:
        row = await db.get(ChatSession, UUID(session_id))
        assert row is not None
        row.level = level
        await db.commit()
    message_id: str = sent.json()["assistant_message"]["id"]
    return message_id


async def _rate(
    client: AsyncClient,
    token: str,
    message_id: str,
    value: int,
    comment: str | None = None,
) -> None:
    body: dict[str, Any] = {"value": value}
    if comment is not None:
        body["comment"] = comment
    response = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json=body,
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text


# --- Сводка -------------------------------------------------------------


async def test_by_level_includes_unknown_for_empty_level(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Срез по уровню: basic/intermediate/advanced + unknown для пустого."""
    token = await _register_and_login(client, "quality_levels")
    basic = await _answer(client, token, db_session, level="basic")
    intermediate = await _answer(
        client, token, db_session, level="intermediate"
    )
    advanced_positive = await _answer(
        client, token, db_session, level="advanced"
    )
    advanced_negative = await _answer(
        client, token, db_session, level="advanced"
    )
    unknown = await _answer(client, token, db_session, level="")

    await _rate(client, token, basic, 1)
    await _rate(client, token, intermediate, -1)
    await _rate(client, token, advanced_positive, 1)
    await _rate(client, token, advanced_negative, -1)
    await _rate(client, token, unknown, -1)

    admin = await _admin_token(client, db_session, "quality_levels_admin")
    response = await client.get(QUALITY_URL, headers=_auth(admin))

    assert response.status_code == 200, response.text
    data = response.json()
    by_level = {row["name"]: row for row in data["by_level"]}
    assert by_level["basic"] == {
        "name": "basic",
        "total": 1,
        "positive": 1,
        "negative": 0,
        "approval_rate": 1.0,
    }
    assert by_level["intermediate"]["total"] == 1
    assert by_level["intermediate"]["negative"] == 1
    assert by_level["advanced"]["total"] == 2
    assert by_level["advanced"]["positive"] == 1
    assert by_level["advanced"]["negative"] == 1
    assert by_level["advanced"]["approval_rate"] == 0.5
    assert by_level["unknown"] == {
        "name": "unknown",
        "total": 1,
        "positive": 0,
        "negative": 1,
        "approval_rate": 0.0,
    }
    assert data["total"] == 5
    assert data["positive"] == 2
    assert data["negative"] == 3


async def test_top_problem_topics_by_category_and_tags(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Топ тем: категории и теги задач, плюс группа «без задачи»."""
    token = await _register_and_login(client, "quality_topics")
    loops = await _make_task(
        db_session,
        title="Циклы",
        category="loops",
        tags=["for", "while"],
    )
    strings = await _make_task(
        db_session,
        title="Строки",
        category="strings",
        tags=["text"],
    )

    loops_one = await _answer(client, token, db_session, task_id=loops.id)
    loops_two = await _answer(client, token, db_session, task_id=loops.id)
    loops_positive = await _answer(
        client, token, db_session, task_id=loops.id
    )
    strings_negative = await _answer(
        client, token, db_session, task_id=strings.id
    )
    no_task = await _answer(client, token, db_session)

    await _rate(client, token, loops_one, -1)
    await _rate(client, token, loops_two, -1)
    await _rate(client, token, loops_positive, 1)
    await _rate(client, token, strings_negative, -1)
    await _rate(client, token, no_task, -1)

    admin = await _admin_token(client, db_session, "quality_topics_admin")
    response = await client.get(QUALITY_URL, headers=_auth(admin))

    assert response.status_code == 200, response.text
    topics = {
        (row["kind"], row["name"]): row["negative"]
        for row in response.json()["top_problem_topics"]
    }
    assert topics[("category", "loops")] == 2
    assert topics[("category", "strings")] == 1
    assert topics[("none", "без задачи")] == 1
    assert topics[("tag", "for")] == 2
    assert topics[("tag", "while")] == 2
    assert topics[("tag", "text")] == 1
    assert all(value > 0 for value in topics.values())


# --- Экспорт ------------------------------------------------------------


async def _negative_fixture(
    client: AsyncClient, db_session: AsyncSession, username: str = "quality_export"
) -> tuple[str, Task, str]:
    """Ученик, задача и два негативных ответа (с задачей и без)."""
    token = await _register_and_login(client, username)
    task = await _make_task(
        db_session,
        title="Условие",
        category="loops",
        tags=["for"],
    )
    with_task = await _answer(
        client, token, db_session, level="intermediate", task_id=task.id
    )
    without_task = await _answer(client, token, db_session, level="")
    positive = await _answer(client, token, db_session, level="basic")
    await _rate(client, token, with_task, -1, "Слишком сложно")
    await _rate(client, token, without_task, -1)
    await _rate(client, token, positive, 1)
    return token, task, with_task


async def test_export_negative_feedback_csv(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """CSV: только негативные оценки, с уровнем и «без задачи»."""
    _, task, _ = await _negative_fixture(client, db_session)
    admin = await _admin_token(client, db_session, "quality_export_admin")

    response = await client.get(
        EXPORT_URL, params={"format": "csv"}, headers=_auth(admin)
    )

    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["X-Export-Limit"] == str(settings.export_max_rows)
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 2
    assert set(rows[0]) == {
        "message_id",
        "comment",
        "provider",
        "model",
        "level",
        "task_id",
        "created_at",
    }
    by_task = {row["task_id"]: row for row in rows}
    assert str(task.id) in by_task
    assert by_task[str(task.id)]["level"] == "intermediate"
    assert by_task[str(task.id)]["comment"] == "Слишком сложно"
    assert by_task[str(task.id)]["provider"] == "fake"
    assert "T" in by_task[str(task.id)]["created_at"]
    assert by_task["без задачи"]["level"] == "unknown"
    assert all(row["message_id"] for row in rows)


async def test_export_negative_feedback_json_and_audit(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """JSON-выгрузка и аудит `quality.exported` без текста комментария."""
    await _negative_fixture(client, db_session, "quality_export_json")
    admin = await _admin_token(client, db_session, "quality_export_json_admin")

    response = await client.get(
        EXPORT_URL, params={"format": "json"}, headers=_auth(admin)
    )

    assert response.status_code == 200, response.text
    payload = json.loads(response.text)
    assert payload["dataset"] == "negative_feedback"
    assert len(payload["items"]) == 2
    assert set(payload["items"][0]) == {
        "message_id",
        "comment",
        "provider",
        "model",
        "level",
        "task_id",
        "created_at",
    }

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "quality.exported")
        )
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].payload == {"format": "json", "limit": settings.export_max_rows}
    assert "Слишком сложно" not in str(audit[0].payload)


async def test_export_respects_max_rows(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Лимит EXPORT_MAX_ROWS обрезает поток и попадает в аудит."""
    await _negative_fixture(client, db_session, "quality_export_limit")
    admin = await _admin_token(client, db_session, "quality_export_limit_admin")
    monkeypatch.setattr(settings, "export_max_rows", 1)

    response = await client.get(
        EXPORT_URL, params={"format": "csv"}, headers=_auth(admin)
    )

    assert response.status_code == 200, response.text
    assert response.headers["X-Export-Limit"] == "1"
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "quality.exported")
        )
    ).scalars().all()
    assert audit[-1].payload["limit"] == 1


async def test_export_requires_admin(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    token = await _register_and_login(client, "quality_export_student")

    response = await client.get(EXPORT_URL, headers=_auth(token))

    assert response.status_code == 403


async def test_export_rejects_unknown_format(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    admin = await _admin_token(client, db_session, "quality_export_badformat")

    response = await client.get(
        EXPORT_URL, params={"format": "xlsx"}, headers=_auth(admin)
    )

    assert response.status_code == 422


async def test_empty_quality_summary(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Пустая сводка возвращает пустые срезы, а не фантомные строки."""
    admin = await _admin_token(client, db_session, "quality_empty_admin")

    response = await client.get(QUALITY_URL, headers=_auth(admin))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["by_level"] == []
    assert data["top_problem_topics"] == []
    assert data["negative_samples"] == []
