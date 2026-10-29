"""
Тесты уровней ассистента (S5-005).

Проверяем переключение уровня пользователя, метаданные уровней, наследование
уровня сессией и fallback, когда файла промпта нет.
"""


import pytest
from httpx import AsyncClient

from app.models.user import UserLevel
from app.services.levels import (
    get_level_info,
    has_prompt,
    list_levels,
    resolve_level,
)

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register_and_login(client: AsyncClient, username: str = "lvluser") -> str:
    """Зарегистрировать пользователя и получить токен"""
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Чистые функции -------------------------------------------------------


def test_list_levels_returns_three_levels_in_order() -> None:
    """Уровней ровно три, от простого к сложному"""
    levels = list_levels()

    assert [info.level for info in levels] == [
        UserLevel.BASIC,
        UserLevel.INTERMEDIATE,
        UserLevel.ADVANCED,
    ]


def test_only_advanced_gives_ready_code() -> None:
    """Готовый код разрешён только на продвинутом уровне"""
    assert get_level_info(UserLevel.BASIC).gives_ready_code is False
    assert get_level_info(UserLevel.INTERMEDIATE).gives_ready_code is False
    assert get_level_info(UserLevel.ADVANCED).gives_ready_code is True


def test_every_level_has_prompt_file() -> None:
    """Для всех трёх уровней есть файл промпта"""
    assert all(has_prompt(level) for level in UserLevel)


def test_resolve_level_falls_back_to_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если промпта нет — откат на базовый уровень"""
    assert resolve_level(UserLevel.ADVANCED) == UserLevel.ADVANCED

    monkeypatch.setattr("app.services.levels.has_prompt", lambda level: False)

    assert resolve_level(UserLevel.ADVANCED) == UserLevel.BASIC


def test_get_level_info_rejects_unknown() -> None:
    """Неизвестный уровень — ValueError"""
    with pytest.raises(ValueError):
        get_level_info("guru")


# --- API ------------------------------------------------------------------


async def test_levels_endpoint_returns_descriptions(client: AsyncClient) -> None:
    """GET /chat/levels отдаёт три уровня с описаниями"""
    response = await client.get("/api/v1/chat/levels")

    assert response.status_code == 200
    levels = response.json()["levels"]
    assert len(levels) == 3
    assert [item["level"] for item in levels] == ["basic", "intermediate", "advanced"]
    assert all(item["title"] and item["description"] for item in levels)


async def test_users_levels_endpoint(client: AsyncClient) -> None:
    """GET /users/levels дублирует справочник для профиля"""
    response = await client.get("/api/v1/users/levels")

    assert response.status_code == 200
    assert len(response.json()["levels"]) == 3


async def test_switch_level_updates_profile(client: AsyncClient) -> None:
    """PATCH /users/me/level меняет уровень пользователя"""
    token = await _register_and_login(client)

    response = await client.patch(
        "/api/v1/users/me/level",
        json={"level": "advanced"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["level"] == "advanced"


async def test_switch_level_affects_new_sessions(client: AsyncClient) -> None:
    """Новая сессия наследует обновлённый уровень пользователя"""
    token = await _register_and_login(client, username="lvlnew")
    await client.patch(
        "/api/v1/users/me/level",
        json={"level": "intermediate"},
        headers=_auth(token),
    )

    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )

    assert session.status_code == 201
    assert session.json()["level"] == "intermediate"


async def test_switch_level_invalid_value(client: AsyncClient) -> None:
    """Неизвестный уровень отклоняется (422)"""
    token = await _register_and_login(client, username="lvlinvalid")

    response = await client.patch(
        "/api/v1/users/me/level",
        json={"level": "guru"},
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_get_my_level_info(client: AsyncClient) -> None:
    """GET /users/me/level отдаёт текущий уровень и описание"""
    token = await _register_and_login(client, username="lvlme")

    response = await client.get("/api/v1/users/me/level", headers=_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "basic"
    assert data["gives_ready_code"] is False


async def test_level_endpoints_require_auth(client: AsyncClient) -> None:
    """Профильные эндпоинты требуют токен"""
    response = await client.get("/api/v1/users/me/level")

    assert response.status_code in (401, 403)


async def test_admin_endpoints_forbidden_for_student(client: AsyncClient) -> None:
    """Студент не может читать чужую карточку через /users/{id}"""
    student_token = await _register_and_login(client, username="student1")
    await _register_and_login(client, username="target1")

    response = await client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000001",
        headers=_auth(student_token),
    )

    assert response.status_code == 403


async def test_session_level_override_differs_from_profile(client: AsyncClient) -> None:
    """Уровень можно задать на конкретную сессию, не меняя профиль"""
    token = await _register_and_login(client, username="lvloverride")

    session = await client.post(
        "/api/v1/chat/sessions", json={"level": "advanced"}, headers=_auth(token)
    )
    profile = await client.get("/api/v1/users/me", headers=_auth(token))

    assert session.json()["level"] == "advanced"
    assert profile.json()["level"] == "basic"
