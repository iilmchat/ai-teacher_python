"""Смена пароля с отзывом refresh-токенов (S45-001).

Все тесты асинхронные, под общим event loop с фикстурой client.
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository

PASSWORD_URL = "/api/v1/users/me/password"
LOGIN_URL = "/api/v1/auth/login"


async def _register_and_login(
    client: AsyncClient, username: str, password: str = "password123"
) -> dict:
    """Регистрация, вход, сырые токены для ручных манипуляций"""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": password,
        },
    )
    login = await client.post(
        LOGIN_URL, data={"username": username, "password": password}
    )
    return login.json()


async def _change(
    client: AsyncClient,
    token: str,
    *,
    current_password: str = "password123",
    new_password: str = "newpassword456",
):
    return await client.post(
        PASSWORD_URL,
        json={
            "current_password": current_password,
            "new_password": new_password,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


async def _refresh_tokens(client: AsyncClient, refresh_token: str):
    """Обновление пары: refresh-токен передаётся в теле JSON (S34-002)."""
    return await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )


async def test_change_password_returns_new_pair(client: AsyncClient) -> None:
    """Успешная смена возвращает новую пару токенов"""
    tokens = await _register_and_login(client, "changepass")

    response = await _change(client, tokens["access_token"])

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_change_password_requires_current_password(client: AsyncClient) -> None:
    """Неверный текущий пароль отклоняется с 400"""
    tokens = await _register_and_login(client, "wrongcurrent")

    response = await _change(
        client, tokens["access_token"], current_password="incorrect1"
    )

    assert response.status_code == 400
    assert "Неверный текущий пароль" in response.json()["detail"]


async def test_change_password_rejects_short_password(client: AsyncClient) -> None:
    """Слишком короткий новый пароль отклоняется с 422"""
    tokens = await _register_and_login(client, "shortnew")

    response = await _change(client, tokens["access_token"], new_password="short")

    assert response.status_code == 422


async def test_change_password_requires_auth(client: AsyncClient) -> None:
    """Без токена маршрут недоступен"""
    response = await client.post(
        PASSWORD_URL,
        json={"current_password": "password123", "new_password": "newpassword456"},
    )

    assert response.status_code in (401, 403)


async def test_change_password_revokes_old_refresh_token(
    client: AsyncClient,
) -> None:
    """Старый refresh-токен после смены не работает"""
    tokens = await _register_and_login(client, "revokerefresh")
    changed = await _change(client, tokens["access_token"])
    assert changed.status_code == 200

    response = await _refresh_tokens(client, tokens["refresh_token"])

    assert response.status_code == 401


async def test_new_refresh_token_works_after_change(client: AsyncClient) -> None:
    """Новая пара из ответа работает, в том числе refresh"""
    tokens = await _register_and_login(client, "newpairworks")
    changed = await _change(client, tokens["access_token"])
    data = changed.json()

    response = await _refresh_tokens(client, data["refresh_token"])

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_old_access_token_still_active_after_change(
    client: AsyncClient,
) -> None:
    """Текущая сессия не страдает: access-токен продолжает работать"""
    tokens = await _register_and_login(client, "stillactive")
    await _change(client, tokens["access_token"])

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "stillactive"


async def test_change_password_bumps_token_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Счётчик версии в БД увеличивается"""
    tokens = await _register_and_login(client, "versionbump")
    await _change(client, tokens["access_token"])

    user = await UserRepository(db_session).get_by_username("versionbump")
    assert user is not None
    assert user.token_version >= 1


async def test_change_password_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Действие попадает в журнал аудита привязанным к пользователю"""
    from sqlalchemy import select

    from app.db.repositories.user import UserRepository
    from app.models.audit import AuditLog

    tokens = await _register_and_login(client, "auditpass")
    await _change(client, tokens["access_token"])

    user = await UserRepository(db_session).get_by_username("auditpass")
    assert user is not None
    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user.password_changed",
                    AuditLog.actor_id == user.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 1
