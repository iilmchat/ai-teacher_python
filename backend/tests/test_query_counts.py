"""Query-count регрессии для ключевых эндпоинтов (S39-002).

Проверяем не абсолютное число запросов (оно зависит от auth/настроек), а
**рост** при увеличении данных: если запросы идут в цикле, количество SELECT
растёт вместе с числом строк. Это ловит N+1 надёжнее жёсткого лимита.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.audit import AuditLog
from app.models.engagement import Notification
from app.models.task import Task, TaskDifficulty, TaskSource
from app.models.user import User, UserLevel, UserRole

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


@contextmanager
def count_selects(engine: Any) -> Iterator[list[str]]:
    """Считать SELECT-запросы, выполненные через engine."""
    statements: list[str] = []

    def before_cursor_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sync_engine = engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


async def _admin_token(client: AsyncClient, db_session: AsyncSession) -> str:
    username = "query_admin"
    await client.post(
        REGISTER_URL,
        json={
            "email": "query_admin@example.com",
            "username": username,
            "password": "password123",
        },
    )
    user = await UserRepository(db_session).get_by_username(username)
    assert user is not None
    await UserRepository(db_session).update(user.id, role=UserRole.ADMIN)
    login = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    assert login.status_code == 200, login.text
    return str(login.json()["access_token"])


async def _student_token(client: AsyncClient) -> str:
    await client.post(
        REGISTER_URL,
        json={
            "email": "query_student@example.com",
            "username": "query_student",
            "password": "password123",
        },
    )
    login = await client.post(
        LOGIN_URL, data={"username": "query_student", "password": "password123"}
    )
    assert login.status_code == 200, login.text
    return str(login.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get(
    client: AsyncClient, engine: Any, path: str, token: str
) -> tuple[int, int]:
    with count_selects(engine) as statements:
        response = await client.get(path, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.status_code, len(statements)


async def test_admin_users_query_count_does_not_grow(
    client: AsyncClient, db_session: AsyncSession, test_engine: Any
) -> None:
    token = await _admin_token(client, db_session)

    for index in range(5):
        db_session.add(
            User(
                email=f"bulk{index}@example.com",
                username=f"bulk{index}",
                hashed_password="x",
                role=UserRole.STUDENT,
                level=UserLevel.BASIC,
            )
        )
    await db_session.commit()
    _, small = await _get(client, test_engine, "/api/v1/admin/users?limit=50", token)

    for index in range(5, 40):
        db_session.add(
            User(
                email=f"bulk{index}@example.com",
                username=f"bulk{index}",
                hashed_password="x",
                role=UserRole.STUDENT,
                level=UserLevel.BASIC,
            )
        )
    await db_session.commit()
    _, large = await _get(client, test_engine, "/api/v1/admin/users?limit=50", token)

    assert large <= small, f"N+1? selects: {small} -> {large}"


async def test_admin_audit_query_count_does_not_grow(
    client: AsyncClient, db_session: AsyncSession, test_engine: Any
) -> None:
    token = await _admin_token(client, db_session)

    for index in range(5):
        db_session.add(
            AuditLog(
                actor_role="admin",
                action="test.action",
                entity_type="test",
                entity_id=str(index),
                payload={},
            )
        )
    await db_session.commit()
    _, small = await _get(client, test_engine, "/api/v1/admin/audit?limit=50", token)

    for index in range(5, 40):
        db_session.add(
            AuditLog(
                actor_role="admin",
                action="test.action",
                entity_type="test",
                entity_id=str(index),
                payload={},
            )
        )
    await db_session.commit()
    _, large = await _get(client, test_engine, "/api/v1/admin/audit?limit=50", token)

    assert large <= small, f"N+1? selects: {small} -> {large}"


async def test_admin_review_query_count_does_not_grow(
    client: AsyncClient, db_session: AsyncSession, test_engine: Any
) -> None:
    token = await _admin_token(client, db_session)

    def add_tasks(start: int, stop: int) -> None:
        for index in range(start, stop):
            db_session.add(
                Task(
                    title=f"Generated {index}",
                    description="desc",
                    difficulty=TaskDifficulty.EASY,
                    category="test",
                    source=TaskSource.GENERATED.value,
                    test_cases=[],
                    hints=[],
                    is_active=False,
                )
            )

    add_tasks(0, 5)
    await db_session.commit()
    _, small = await _get(
        client, test_engine, "/api/v1/admin/tasks/review?limit=50", token
    )

    add_tasks(5, 30)
    await db_session.commit()
    _, large = await _get(
        client, test_engine, "/api/v1/admin/tasks/review?limit=50", token
    )

    assert large <= small, f"N+1? selects: {small} -> {large}"


async def test_notifications_query_count_does_not_grow(
    client: AsyncClient, db_session: AsyncSession, test_engine: Any
) -> None:
    token = await _student_token(client)
    user = await UserRepository(db_session).get_by_username("query_student")
    assert user is not None

    for index in range(5):
        db_session.add(
            Notification(
                user_id=user.id,
                type="system",
                payload={"index": index},
            )
        )
    await db_session.commit()
    _, small = await _get(
        client, test_engine, "/api/v1/me/notifications?limit=100", token
    )

    for index in range(5, 35):
        db_session.add(
            Notification(
                user_id=user.id,
                type="system",
                payload={"index": index},
            )
        )
    await db_session.commit()
    _, large = await _get(
        client, test_engine, "/api/v1/me/notifications?limit=100", token
    )

    assert large <= small, f"N+1? selects: {small} -> {large}"
