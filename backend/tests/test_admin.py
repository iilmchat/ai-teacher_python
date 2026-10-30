"""
Тесты Admin API (S10-004, S10-005).

Админ создаётся напрямую в БД: эндпоинта «стать админом» нет по соображениям
безопасности (KI-011).
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.task import Task, TaskDifficulty
from app.models.user import UserRole

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


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
    client: AsyncClient, db: AsyncSession, username: str = "admin1"
) -> str:
    token = await _register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Доступ -------------------------------------------------------------


@pytest.mark.parametrize("role", ["student"])
async def test_student_forbidden(client: AsyncClient, role: str) -> None:
    """Студент не попадает в админку"""
    token = await _register_and_login(client, f"notadmin_{role}")

    response = await client.get("/api/v1/admin/users", headers=_auth(token))

    assert response.status_code == 403


async def test_anonymous_forbidden(client: AsyncClient) -> None:
    """Без токена админка недоступна"""
    response = await client.get("/api/v1/admin/analytics")

    assert response.status_code in (401, 403)


# --- Пользователи -------------------------------------------------------


async def test_admin_lists_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Админ видит список пользователей"""
    token = await _admin_token(client, db_session)
    await _register_and_login(client, "pupil1")

    response = await client.get("/api/v1/admin/users", headers=_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert any(item["username"] == "pupil1" for item in data["items"])


async def test_admin_filters_by_role_and_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Фильтр по роли и поиск по имени"""
    token = await _admin_token(client, db_session, "admin2")
    await _register_and_login(client, "searched_student")

    by_role = await client.get(
        "/api/v1/admin/users", params={"role": "admin"}, headers=_auth(token)
    )
    by_search = await client.get(
        "/api/v1/admin/users", params={"search": "searched"}, headers=_auth(token)
    )

    assert all(item["role"] == "admin" for item in by_role.json()["items"])
    assert [item["username"] for item in by_search.json()["items"]] == [
        "searched_student"
    ]


async def test_admin_changes_role_and_level(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Админ меняет роль и уровень пользователя"""
    token = await _admin_token(client, db_session, "admin3")
    await _register_and_login(client, "promoted")
    target = await UserRepository(db_session).get_by_username("promoted")
    assert target is not None

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"role": "teacher", "level": "advanced"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "teacher"
    assert response.json()["level"] == "advanced"


async def test_admin_cannot_demote_self(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Нельзя понизить собственную роль — иначе можно потерять доступ"""
    token = await _admin_token(client, db_session, "admin4")
    me = await UserRepository(db_session).get_by_username("admin4")
    assert me is not None

    response = await client.patch(
        f"/api/v1/admin/users/{me.id}", json={"role": "student"}, headers=_auth(token)
    )

    assert response.status_code == 400
    assert "собственную" in response.json()["detail"]


async def test_admin_cannot_delete_self(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Нельзя удалить собственную учётную запись"""
    token = await _admin_token(client, db_session, "admin5")
    me = await UserRepository(db_session).get_by_username("admin5")
    assert me is not None

    response = await client.delete(
        f"/api/v1/admin/users/{me.id}", headers=_auth(token)
    )

    assert response.status_code == 400


async def test_admin_deletes_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Админ удаляет пользователя"""
    token = await _admin_token(client, db_session, "admin6")
    await _register_and_login(client, "to_delete")
    target = await UserRepository(db_session).get_by_username("to_delete")
    assert target is not None

    response = await client.delete(
        f"/api/v1/admin/users/{target.id}", headers=_auth(token)
    )
    listing = await client.get(
        "/api/v1/admin/users", params={"search": "to_delete"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert listing.json()["total"] == 0


async def test_admin_missing_user_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующий пользователь — 404"""
    token = await _admin_token(client, db_session, "admin7")

    response = await client.get("/api/v1/admin/users", headers=_auth(token))
    patch_response = await client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
        json={"role": "teacher"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert patch_response.status_code == 404


# --- Задачи и аналитика --------------------------------------------------


async def test_admin_lists_all_tasks_including_inactive(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Админ видит и неактивные задачи"""
    token = await _admin_token(client, db_session, "admin8")
    db_session.add(
        Task(
            title="Скрытая задача",
            description="Неактивная задача для проверки админки.",
            difficulty=TaskDifficulty.EASY,
            category="test",
            test_cases=[{"input": "", "expected_output": "x"}],
            hints=[],
            is_active=False,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/tasks", headers=_auth(token))

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Скрытая задача" in titles
    assert response.json()["total"] >= 1


async def test_analytics_structure(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Аналитика содержит все разделы сводки, включая метрики LLM"""
    token = await _admin_token(client, db_session, "admin9")

    response = await client.get("/api/v1/admin/analytics", headers=_auth(token))

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert set(data) == {
        "users",
        "tasks",
        "learning",
        "activity",
        "llm",
        "cache",
        "generated_at",
    }
    assert data["users"]["total"] >= 1
    assert set(data["users"]["by_role"]) == {"student", "teacher", "admin"}
    assert data["tasks"]["total"] >= 0
    assert data["learning"]["attempts"] >= 0
    assert data["activity"]["messages"] >= 0
    assert set(data["llm"]) == {"last_hour", "last_24h", "fallback_used", "recorded_at"}
    assert data["llm"]["last_24h"]["window_hours"] == 24
    assert data["llm"]["last_hour"]["requests"] >= 0
    assert set(data["cache"]) == {
        "enabled",
        "hits",
        "misses",
        "hit_rate",
        "sets",
        "invalidations",
        "errors",
    }
    assert data["cache"]["hits"] >= 0
    assert 0.0 <= data["cache"]["hit_rate"] <= 1.0
