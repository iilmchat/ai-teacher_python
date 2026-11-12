"""Активные сессии и отзыв refresh-токенов (S45-005, закрывает KI-028)."""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token
from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
SESSIONS_URL = "/api/v1/users/me/sessions"
REVOKE_OTHERS_URL = "/api/v1/users/me/sessions/revoke-others"


async def _register(client: AsyncClient, username: str) -> None:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
    )


async def _login(client: AsyncClient, username: str) -> dict:
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _sessions(client: AsyncClient, access_token: str) -> list[dict]:
    response = await client.get(
        SESSIONS_URL, headers=_auth_header(access_token)
    )
    assert response.status_code == 200
    return response.json()


async def test_login_creates_listed_session(client: AsyncClient) -> None:
    """Вход создаёт сессию: она одна, текущая, с user-agent"""
    await _register(client, "sesslist")
    tokens = await _login(client, "sesslist")

    sessions = await _sessions(client, tokens["access_token"])

    assert len(sessions) == 1
    session = sessions[0]
    assert session["current"] is True
    assert session["created_at"]
    assert session["last_used_at"]
    assert session["user_agent"]
    assert "id" in session


async def test_two_logins_two_sessions(client: AsyncClient) -> None:
    """Два входа — две сессии; текущая помечена только одна"""
    await _register(client, "twologins")
    await _login(client, "twologins")
    second = await _login(client, "twologins")

    sessions = await _sessions(client, second["access_token"])

    assert len(sessions) == 2
    assert sum(1 for item in sessions if item["current"]) == 1


async def test_revoke_other_session(client: AsyncClient) -> None:
    """Отзыв конкретной сессии: её refresh-токен отклоняется, остаётся одна"""
    await _register(client, "revokeone")
    first = await _login(client, "revokeone")
    second = await _login(client, "revokeone")

    sessions = await _sessions(client, second["access_token"])
    other = next(item for item in sessions if not item["current"])

    revoked = await client.delete(
        f"{SESSIONS_URL}/{other['id']}",
        headers=_auth_header(second["access_token"]),
    )
    assert revoked.status_code == 204

    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert refresh.status_code == 401

    remaining = await _sessions(client, second["access_token"])
    assert len(remaining) == 1
    assert remaining[0]["current"] is True

    # Текущая сессия продолжает обновляться
    current_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert current_refresh.status_code == 200


async def test_cannot_revoke_current_session(client: AsyncClient) -> None:
    """Текущую сессию через список не отозвать — только выход"""
    await _register(client, "revokecurrent")
    tokens = await _login(client, "revokecurrent")

    sessions = await _sessions(client, tokens["access_token"])
    current = next(item for item in sessions if item["current"])

    response = await client.delete(
        f"{SESSIONS_URL}/{current['id']}",
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 400


async def test_cannot_revoke_foreign_session(client: AsyncClient) -> None:
    """Чужую сессию не видно и не отозвать (404)"""
    await _register(client, "owneruser")
    await _register(client, "intruder")
    owner = await _login(client, "owneruser")
    intruder = await _login(client, "intruder")

    owner_sessions = await _sessions(client, owner["access_token"])

    response = await client.delete(
        f"{SESSIONS_URL}/{owner_sessions[0]['id']}",
        headers=_auth_header(intruder["access_token"]),
    )

    assert response.status_code == 404
    assert len(await _sessions(client, owner["access_token"])) == 1


async def test_refresh_rotates_jti(client: AsyncClient) -> None:
    """Refresh ротирует сессию: старый refresh-токен больше не работает"""
    await _register(client, "rotatejti")
    tokens = await _login(client, "rotatejti")

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()

    old_again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert old_again.status_code == 401

    new_again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert new_again.status_code == 200

    # Ротация не плодит сессии
    assert len(await _sessions(client, new_tokens["access_token"])) == 1


async def test_legacy_refresh_without_jti_still_works(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Токен старого формата (без jti) не разлогинивает после деплоя"""
    await _register(client, "legacyrefresh")
    await _login(client, "legacyrefresh")

    user = (
        (await db_session.execute(select(User).where(User.username == "legacyrefresh")))
        .scalars()
        .one()
    )
    legacy = create_refresh_token({"sub": str(user.id), "tv": user.token_version})

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": legacy}
    )

    assert response.status_code == 200
    assert "refresh_token" in response.json()


async def test_revoke_others_signs_out_everywhere(client: AsyncClient) -> None:
    """«Выйти на всех устройствах»: чужие refresh мертвы, текущее живо"""
    await _register(client, "everywhere")
    first = await _login(client, "everywhere")
    second = await _login(client, "everywhere")

    response = await client.post(
        REVOKE_OTHERS_URL, headers=_auth_header(second["access_token"])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["revoked"] == 2
    assert "access_token" in data
    assert "refresh_token" in data

    # Обе старые сессии больше не обновляются
    for tokens in (first, second):
        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refresh.status_code == 401

    # Текущая сессия — одна, и она новая (до ротации refresh-токена)
    sessions = await _sessions(client, data["access_token"])
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    # Новая пара текущего устройства работает
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert refresh.status_code == 200


async def test_revoke_others_bumps_token_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Версия refresh-токенов увеличивается — KI-028 закрыт"""
    await _register(client, "everywherever")
    tokens = await _login(client, "everywherever")

    await client.post(REVOKE_OTHERS_URL, headers=_auth_header(tokens["access_token"]))

    user = (
        (
            await db_session.execute(
                select(User).where(User.username == "everywherever")
            )
        )
        .scalars()
        .one()
    )
    assert user.token_version >= 1


async def test_revoke_others_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Действие «выйти везде» попадает в журнал аудита"""
    from app.models.audit import AuditLog

    await _register(client, "auditsessions")
    tokens = await _login(client, "auditsessions")
    user = (
        (
            await db_session.execute(
                select(User).where(User.username == "auditsessions")
            )
        )
        .scalars()
        .one()
    )

    await client.post(REVOKE_OTHERS_URL, headers=_auth_header(tokens["access_token"]))

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user.sessions_revoked",
                    AuditLog.actor_id == user.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 1


async def test_sessions_require_auth(client: AsyncClient) -> None:
    """Без токена список сессий недоступен"""
    response = await client.get(SESSIONS_URL)
    assert response.status_code in (401, 403)
