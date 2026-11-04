"""
Tests for authentication endpoints (S3-005).

Все тесты асинхронные: используется общий event loop с фикстурой client,
что необходимо для asyncpg (соединение привязано к loop).
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register(
    client: AsyncClient,
    email: str,
    username: str,
    password: str = "password123",
):
    """Хелпер регистрации пользователя"""
    return await client.post(
        REGISTER_URL,
        json={"email": email, "username": username, "password": password},
    )


async def test_register_user(client: AsyncClient) -> None:
    """Успешная регистрация возвращает профиль без пароля"""
    response = await _register(client, "test@example.com", "testuser", "testpassword123")

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert data["role"] == "student"
    assert data["level"] == "basic"
    assert "id" in data
    assert "hashed_password" not in data


async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Повторный email отклоняется с 400"""
    await _register(client, "duplicate@example.com", "user1")
    response = await _register(client, "duplicate@example.com", "user2")

    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


async def test_register_duplicate_username(client: AsyncClient) -> None:
    """Повторный username отклоняется с 400"""
    await _register(client, "user1@example.com", "duplicateuser")
    response = await _register(client, "user2@example.com", "duplicateuser")

    assert response.status_code == 400
    assert "Username already taken" in response.json()["detail"]


async def test_register_invalid_email(client: AsyncClient) -> None:
    """Некорректный email отклоняется с 422"""
    response = await _register(client, "not-an-email", "invalidmail")

    assert response.status_code == 422


async def test_register_short_password(client: AsyncClient) -> None:
    """Слишком короткий пароль отклоняется с 422"""
    response = await _register(client, "short@example.com", "shortpass", "123")

    assert response.status_code == 422


async def test_login_success(client: AsyncClient) -> None:
    """Вход по username возвращает пару токенов"""
    await _register(client, "login@example.com", "loginuser")

    response = await client.post(
        LOGIN_URL,
        data={"username": "loginuser", "password": "password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "loginuser"


async def test_login_with_email(client: AsyncClient) -> None:
    """Вход возможен по email"""
    await _register(client, "email@example.com", "emailuser")

    response = await client.post(
        LOGIN_URL,
        data={"username": "email@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client: AsyncClient) -> None:
    """Неверный пароль — 401"""
    await _register(client, "wrongpass@example.com", "wrongpassuser", "correctpassword")

    response = await client.post(
        LOGIN_URL,
        data={"username": "wrongpassuser", "password": "wrongpassword"},
    )

    assert response.status_code == 401


async def test_login_unknown_user(client: AsyncClient) -> None:
    """Несуществующий пользователь — 401"""
    response = await client.post(
        LOGIN_URL,
        data={"username": "ghost", "password": "password123"},
    )

    assert response.status_code == 401


async def _login(client: AsyncClient, username: str, password: str = "password123") -> str:
    """Хелпер получения access token"""
    response = await client.post(LOGIN_URL, data={"username": username, "password": password})
    return response.json()["access_token"]


async def test_get_me(client: AsyncClient) -> None:
    """GET /auth/me возвращает текущего пользователя"""
    await _register(client, "me@example.com", "meuser")
    token = await _login(client, "meuser")

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "meuser"


async def test_refresh_token(client: AsyncClient) -> None:
    """Refresh token выдаёт новую пару токенов"""
    await _register(client, "refresh@example.com", "refreshuser")
    login_response = await client.post(
        LOGIN_URL,
        data={"username": "refreshuser", "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_with_access_token_rejected(client: AsyncClient) -> None:
    """Access token нельзя использовать как refresh"""
    await _register(client, "mix@example.com", "mixuser")
    access_token = await _login(client, "mixuser")

    response = await client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": access_token},
    )

    assert response.status_code == 401


async def test_protected_route_without_token(client: AsyncClient) -> None:
    """Без токена защищённый маршрут недоступен"""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code in (401, 403)


async def test_update_me(client: AsyncClient) -> None:
    """PATCH /auth/me обновляет профиль"""
    await _register(client, "patch@example.com", "patchuser")
    token = await _login(client, "patchuser")

    response = await client.patch(
        "/api/v1/auth/me",
        json={"level": "intermediate"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["level"] == "intermediate"


# --- v0.3.3 (KI-026): неактивный аккаунт не получает токены ------------------


async def _deactivate(db_session: AsyncSession, username: str) -> None:
    user = await UserRepository(db_session).get_by_username(username)
    assert user is not None
    await UserRepository(db_session).update(user.id, is_active=False)


async def test_login_rejects_inactive_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Заблокированный аккаунт не входит даже с верным паролем"""
    await _register(client, "inactive@example.com", "inactiveuser")
    await _deactivate(db_session, "inactiveuser")

    response = await client.post(
        LOGIN_URL, data={"username": "inactiveuser", "password": "password123"}
    )

    assert response.status_code == 401


async def test_refresh_rejected_for_inactive_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Refresh-токен неактивного пользователя не выдаёт новую пару"""
    await _register(client, "inactive2@example.com", "inactive2")
    login = await client.post(
        LOGIN_URL, data={"username": "inactive2", "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]
    await _deactivate(db_session, "inactive2")

    response = await client.post(
        "/api/v1/auth/refresh", params={"refresh_token": refresh_token}
    )

    assert response.status_code == 401


async def test_refresh_rejected_after_account_deletion(client: AsyncClient) -> None:
    """Refresh-токен не переживает DELETE /auth/me"""
    await _register(client, "gone@example.com", "goneuser")
    login = await client.post(
        LOGIN_URL, data={"username": "goneuser", "password": "password123"}
    )
    tokens = login.json()

    deleted = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "password123"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert deleted.status_code == 204, deleted.text

    response = await client.post(
        "/api/v1/auth/refresh", params={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 401
