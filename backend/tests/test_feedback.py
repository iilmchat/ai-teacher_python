"""
Тесты оценок ответов ассистента (S43-003).

Оценка принадлежит ученику: чужое сообщение недоступно (403), на пару
«сообщение × ученик» оценка всегда одна, а агрегаты видит только админ.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.user import UserRole
from tests.fake_llm import FakeProvider, install_fake_provider, uninstall_fake_provider

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture
def fake_provider() -> FakeProvider:
    """Фейковый LLM-провайдер (ответы без обращения к сети)"""
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
    client: AsyncClient, db: AsyncSession, username: str = "fbadmin"
) -> str:
    """Токен администратора: роль выставляется напрямую в БД"""
    token = await _register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


async def _answer(
    client: AsyncClient, token: str, content: str = "Вопрос?"
) -> tuple[str, str]:
    """Создать сессию, отправить сообщение; вернуть (id сессии, id ответа)"""
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    sent = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": content},
        headers=_auth(token),
    )
    assert sent.status_code == 201, sent.text
    return session_id, sent.json()["assistant_message"]["id"]


async def test_feedback_is_saved_and_changed(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Оценка ставится и меняется: на сообщение ученика она одна"""
    token = await _register_and_login(client, "fbuser")
    session_id, message_id = await _answer(client, token)

    first = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": 1},
        headers=_auth(token),
    )
    assert first.status_code == 201, first.text
    assert first.json()["value"] == 1

    second = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": -1},
        headers=_auth(token),
    )
    assert second.status_code == 201, second.text
    assert second.json()["value"] == -1

    listed = await client.get(
        f"/api/v1/chat/sessions/{session_id}/feedback", headers=_auth(token)
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 1
    assert items[0]["value"] == -1


async def test_feedback_keeps_comment(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Комментарий ученика сохраняется"""
    token = await _register_and_login(client, "fbcomment")
    _, message_id = await _answer(client, token)

    response = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": -1, "comment": "  Не понял объяснение  "},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["comment"] == "Не понял объяснение"


async def test_feedback_comment_too_long_rejected(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Комментарий длиннее 500 символов — 422"""
    token = await _register_and_login(client, "fblong")
    _, message_id = await _answer(client, token)

    response = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": 1, "comment": "x" * 501},
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_feedback_on_foreign_message_forbidden(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Чужое сообщение оценить нельзя (403)"""
    owner_token = await _register_and_login(client, "fbowner")
    _, message_id = await _answer(client, owner_token)
    other_token = await _register_and_login(client, "fbintruder")

    response = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": -1},
        headers=_auth(other_token),
    )

    assert response.status_code == 403


async def test_feedback_on_unknown_message_returns_404(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Несуществующее сообщение — 404"""
    token = await _register_and_login(client, "fb404")

    response = await client.post(
        f"/api/v1/chat/messages/{uuid4()}/feedback",
        json={"value": 1},
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_feedback_on_user_message_rejected(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Оценить вопрос ученика нельзя (422)"""
    token = await _register_and_login(client, "fbquestion")
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )
    session_id = session.json()["id"]
    sent = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Мой вопрос"},
        headers=_auth(token),
    )
    question_id = sent.json()["user_message"]["id"]

    response = await client.post(
        f"/api/v1/chat/messages/{question_id}/feedback",
        json={"value": 1},
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_feedback_can_be_removed(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Оценку можно снять"""
    token = await _register_and_login(client, "fbremove")
    _, message_id = await _answer(client, token)
    await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": 1},
        headers=_auth(token),
    )

    deleted = await client.delete(
        f"/api/v1/chat/messages/{message_id}/feedback", headers=_auth(token)
    )

    assert deleted.status_code == 204
    again = await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": -1},
        headers=_auth(token),
    )
    assert again.status_code == 201


async def test_session_feedback_list(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Список моих оценок по сессии"""
    token = await _register_and_login(client, "fblist")
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )
    session_id = session.json()["id"]
    sent = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Вопрос"},
        headers=_auth(token),
    )
    message_id = sent.json()["assistant_message"]["id"]
    await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": 1, "comment": "Понятно"},
        headers=_auth(token),
    )

    listed = await client.get(
        f"/api/v1/chat/sessions/{session_id}/feedback", headers=_auth(token)
    )

    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 1
    assert items[0]["message_id"] == message_id
    assert items[0]["comment"] == "Понятно"


async def test_session_feedback_of_foreign_session_forbidden(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Оценки чужой сессии не видны (403)"""
    owner_token = await _register_and_login(client, "fbsessowner")
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(owner_token)
    )
    session_id = session.json()["id"]
    other_token = await _register_and_login(client, "fbsessother")

    response = await client.get(
        f"/api/v1/chat/sessions/{session_id}/feedback", headers=_auth(other_token)
    )

    assert response.status_code == 403


async def test_admin_quality_summary(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Админ видит агрегаты качества по провайдеру и модели"""
    token = await _register_and_login(client, "fbstudent")
    _, message_id = await _answer(client, token)
    await client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"value": -1, "comment": "Слишком сложно"},
        headers=_auth(token),
    )

    admin_token = await _admin_token(client, db_session, "fbqualityadmin")
    response = await client.get(
        "/api/v1/admin/quality", headers=_auth(admin_token)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["negative"] == 1
    assert data["positive"] == 0
    assert data["approval_rate"] == 0.0
    assert data["by_provider"]
    assert data["by_provider"][0]["name"] == "fake"
    assert data["negative_samples"][0]["comment"] == "Слишком сложно"
    assert data["negative_samples"][0]["content"]


async def test_quality_summary_forbidden_for_student(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Сводка качества доступна только админу"""
    token = await _register_and_login(client, "fbplain")

    response = await client.get("/api/v1/admin/quality", headers=_auth(token))

    assert response.status_code == 403
