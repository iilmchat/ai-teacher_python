"""Правка профиля и удаление аккаунта из UI (S45-002).

DELETE /auth/me реализован в S26-004; здесь проверяются сценарии, доступные
новому интерфейсу: отказ с неверным паролем, анонимизация, сохранение
прогресса, уведомление на старый адрес при смене e-mail.
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


async def _register_and_login(
    client: AsyncClient, username: str, password: str = "password123"
) -> dict:
    await client.post(
        REGISTER_URL,
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


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_update_profile_email_and_username(client: AsyncClient) -> None:
    """PATCH /auth/me меняет e-mail и имя одним запросом"""
    tokens = await _register_and_login(client, "editprofile")

    response = await client.patch(
        "/api/v1/auth/me",
        json={
            "email": "newaddress@example.com",
            "username": "editprofile2",
        },
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newaddress@example.com"
    assert data["username"] == "editprofile2"


async def test_update_profile_taken_email(client: AsyncClient) -> None:
    """Занятый e-mail отклоняется с 400"""
    await _register_and_login(client, "takesfirst")
    tokens = await _register_and_login(client, "takessecond")

    response = await client.patch(
        "/api/v1/auth/me",
        json={"email": "takesfirst@example.com"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 400


async def test_update_profile_sends_notice_to_old_email(
    client: AsyncClient, monkeypatch
) -> None:
    """Смена e-mail уведомляет старый адрес (best-effort)"""
    calls: list[str] = []

    class RecordingSender:
        async def send(self, *, to: str, subject: str, body: str) -> None:
            calls.append(to)

    def fake_sender():
        return RecordingSender()

    monkeypatch.setattr(
        "app.services.email.get_email_sender", fake_sender
    )

    tokens = await _register_and_login(client, "notice")
    await client.patch(
        "/api/v1/auth/me",
        json={"email": "moved@example.com"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert calls == ["notice@example.com"]


async def test_update_profile_notice_failure_does_not_break_request(
    client: AsyncClient, monkeypatch
) -> None:
    """Сбой отправки письма не ломает PATCH"""
    class BrokenSender:
        async def send(self, **kwargs) -> None:
            raise RuntimeError("smtp down")

    monkeypatch.setattr(
        "app.services.email.get_email_sender", lambda: BrokenSender()
    )

    tokens = await _register_and_login(client, "smtpdown")
    response = await client.patch(
        "/api/v1/auth/me",
        json={"email": "moved2@example.com"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "moved2@example.com"


async def test_delete_account_wrong_password(client: AsyncClient) -> None:
    """Неверный пароль отменяет удаление (400)"""
    tokens = await _register_and_login(client, "wrongdel")

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "incorrect1"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 400
    me = await client.get(
        "/api/v1/auth/me", headers=_auth_header(tokens["access_token"])
    )
    assert me.status_code == 200


async def test_delete_account_requires_password(client: AsyncClient) -> None:
    """Без пароля удаление невозможно"""
    tokens = await _register_and_login(client, "nopassdel")

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 422


async def test_delete_account_anonymizes_and_blocks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Удаление обезличивает аккаунт, блокирует вход и сохраняет вход в журнал"""
    username = "anondel"
    tokens = await _register_and_login(client, username)
    user_id = tokens["user"]["id"]

    deleted = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "password123"},
        headers=_auth_header(tokens["access_token"]),
    )
    assert deleted.status_code == 204

    row = await db_session.get(User, user_id)
    assert row is not None
    assert row.is_active is False
    assert row.username.startswith("deleted_")
    assert row.email.startswith("deleted_")

    # Со старым access-токеном защищённые маршруты недоступны
    me = await client.get(
        "/api/v1/auth/me", headers=_auth_header(tokens["access_token"])
    )
    assert me.status_code == 401


async def test_delete_account_revokes_refresh_token(client: AsyncClient) -> None:
    """Refresh-токен не переживает удаление (и версию, и неактивность)"""
    tokens = await _register_and_login(client, "refreshdel")

    deleted = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "password123"},
        headers=_auth_header(tokens["access_token"]),
    )
    assert deleted.status_code == 204

    refresh = await client.post(
        "/api/v1/auth/refresh", params={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401
