"""
Тесты чат-сервиса и Chat API (S4-007).

LLM подменяется фейковым провайдером: тесты не ходят в сеть (RULES §4.4).
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.prompt_builder import load_system_prompt

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


class FakeProvider(LLMProvider):
    """Фейковый провайдер, запоминающий переданные сообщения"""

    name = "fake"

    def __init__(
        self,
        reply: str = "Попробуй проверить условие.\n\n```python\nprint(1)\n```",
    ) -> None:
        self.reply = reply
        self.calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(messages)
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append(messages)
        for part in ("Привет", ", ", "ученик!"):
            yield part


@pytest.fixture
def fake_provider() -> Iterator[FakeProvider]:
    """Фейковый LLM-провайдер и его установка в приложение"""
    provider = FakeProvider()
    from app.api.v1.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_llm_provider, None)


async def _register_and_login(
    client: AsyncClient, username: str = "chatuser", email: str | None = None
) -> str:
    """Зарегистрировать пользователя и вернуть access-токен"""
    email = email or f"{username}@example.com"
    await client.post(
        REGISTER_URL,
        json={"email": email, "username": username, "password": "password123"},
    )
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    token: str = response.json()["access_token"]
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_session(
    client: AsyncClient, token: str, level: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if level is not None:
        payload["level"] = level
    response = await client.post(
        "/api/v1/chat/sessions", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_create_session_uses_user_level(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Сессия создаётся с уровнем пользователя по умолчанию"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    assert session["level"] == "basic"
    assert session["id"]


async def test_create_session_with_level(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Уровень можно задать при создании сессии"""
    token = await _register_and_login(client)
    session = await _create_session(client, token, level="advanced")

    assert session["level"] == "advanced"


async def test_create_session_invalid_level(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Неизвестный уровень отклоняется схемой (422)"""
    token = await _register_and_login(client)
    response = await client.post(
        "/api/v1/chat/sessions", json={"level": "super"}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_list_and_delete_sessions(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Список сессий и удаление"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    listed = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [session["id"]]

    deleted = await client.delete(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )
    assert deleted.status_code == 204

    after = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert after.json() == []


async def test_send_message_returns_pair_and_extracts_code(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Ответ содержит пару сообщений, блоки кода извлечены"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Почему мой код не работает?"},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user_message"]["role"] == "user"
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["content"] == fake_provider.reply
    assert data["assistant_message"]["code_blocks"] == ["print(1)"]


async def test_prompt_contains_level_system_message(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """В LLM уходит системный промпт выбранного уровня"""
    token = await _register_and_login(client)
    session = await _create_session(client, token, level="intermediate")

    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Что такое цикл while?"},
        headers=_auth(token),
    )

    assert fake_provider.calls, "провайдер не вызывался"
    messages = fake_provider.calls[0]
    assert messages[0].role == "system"
    assert messages[0].content == load_system_prompt("intermediate")
    assert messages[-1].role == "user"
    assert messages[-1].content == "Что такое цикл while?"


async def test_history_is_passed_to_llm(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Второй запрос получает историю предыдущего обмена"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Первый вопрос"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Второй вопрос"},
        headers=_auth(token),
    )

    last_call = fake_provider.calls[-1]
    contents = [(m.role, m.content) for m in last_call]
    assert ("user", "Первый вопрос") in contents
    assert ("assistant", fake_provider.reply) in contents
    # Текущий вопрос не должен дублироваться в истории
    assert [c for c in contents if c == ("user", "Второй вопрос")] == [
        ("user", "Второй вопрос")
    ]


async def test_session_with_messages_returns_history(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """GET сессии возвращает всю переписку"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)
    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Вопрос"},
        headers=_auth(token),
    )

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]


async def test_empty_message_rejected(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Пустое сообщение не принимается"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": ""},
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_whitespace_message_rejected(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Сообщение из пробелов отклоняется сервисом (422 через AppError)"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "    "},
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_other_user_session_forbidden(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Чужую сессию нельзя прочитать, отправить в неё сообщение или удалить"""
    owner_token = await _register_and_login(client, username="owner", email="owner@example.com")
    session = await _create_session(client, owner_token)

    other_token = await _register_and_login(
        client, username="intruder", email="intruder@example.com"
    )

    get_response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(other_token)
    )
    post_response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "чужой вопрос"},
        headers=_auth(other_token),
    )
    delete_response = await client.delete(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(other_token)
    )

    assert get_response.status_code == 403
    assert post_response.status_code == 403
    assert delete_response.status_code == 403


async def test_missing_session_returns_404(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Несуществующая сессия — 404"""
    token = await _register_and_login(client)

    response = await client.get(
        "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_chat_requires_auth(client: AsyncClient, fake_provider: FakeProvider) -> None:
    """Без токена чат недоступен"""
    response = await client.get("/api/v1/chat/sessions")

    assert response.status_code in (401, 403)


async def test_assistant_message_has_prompt_metadata(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """В метаданных ответа — провайдер, модель и версия промпта (S12-006)"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Как работает цикл while?"},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    assistant = response.json()["assistant_message"]
    assert assistant["metadata"]["provider"] == "fake"
    assert assistant["metadata"]["prompt_version"] == 1
    assert "model" in assistant["metadata"]
    assert assistant["warnings"] == []
    assert response.json()["user_message"]["metadata"] == {}


async def test_basic_full_solution_is_flagged(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Готовое решение на базовом уровне помечается предупреждением (S12-005)"""
    fake_provider.reply = (
        "Вот решение:\n\n```python\nn = int(input())\n"
        "total = sum(range(n + 1))\nprint(total)\n```"
    )
    token = await _register_and_login(client)
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Напиши программу"},
        headers=_auth(token),
    )

    assistant = response.json()["assistant_message"]
    assert "basic_full_solution" in assistant["warnings"]
    assert assistant["metadata"]["warnings"] == assistant["warnings"]


async def test_advanced_level_is_not_flagged(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Продвинутому уровню готовый код разрешён"""
    fake_provider.reply = "```python\nn = int(input())\nprint(n)\n```"
    token = await _register_and_login(client)
    session = await _create_session(client, token, level="advanced")

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Напиши программу"},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["assistant_message"]["warnings"] == []


async def test_session_history_returns_metadata(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """GET сессии отдаёт метаданные каждого ответа (для разбора инцидентов)"""
    token = await _register_and_login(client)
    session = await _create_session(client, token)
    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Вопрос"},
        headers=_auth(token),
    )

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )

    assistant = response.json()["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["metadata"]["provider"] == "fake"
    assert "prompt_version" in assistant["metadata"]
