"""
Тесты выгрузки диалога чата и личных настроек (S43-004).

Выгрузка отдаётся в двух форматах: Markdown-транскрипт и JSON, совместимый
с `GET /chat/sessions/{id}`. Чужая сессия недоступна (403).
"""

import json
from typing import Any

import pytest
from httpx import AsyncClient

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


async def _session_with_dialog(
    client: AsyncClient, token: str, content: str = "Как работает цикл for?"
) -> dict[str, Any]:
    """Сессия с одним вопросом и ответом ассистента"""
    session = await client.post(
        "/api/v1/chat/sessions", json={}, headers=_auth(token)
    )
    assert session.status_code == 201, session.text
    data = session.json()
    sent = await client.post(
        f"/api/v1/chat/sessions/{data['id']}/messages",
        json={"content": content},
        headers=_auth(token),
    )
    assert sent.status_code == 201, sent.text
    return data


async def test_export_markdown_keeps_roles_and_code(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Markdown-транскрипт: роли, вопрос и блок кода на месте"""
    token = await _register_and_login(client, "expmd")
    session = await _session_with_dialog(client, token)

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}/export?format=md",
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    assert "text/markdown" in response.headers["content-type"]
    text = response.text
    assert "# Диалог с ассистентом" in text
    assert "## Ученик" in text
    assert "## Ассистент" in text
    assert "Как работает цикл for?" in text
    assert "```python" in text
    assert "print(1)" in text
    assert "attachment; filename=" in response.headers["content-disposition"]


async def test_export_markdown_keeps_special_characters(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Спецсимволы не экранируются: транскрипт остаётся читаемым"""
    token = await _register_and_login(client, "expspecial")
    session = await _session_with_dialog(
        client, token, content="Что значит a < b && c > d? *звёзды* _подчёркивание_"
    )

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}/export?format=md",
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    assert "a < b && c > d? *звёзды* _подчёркивание_" in response.text


async def test_export_json_matches_session_api(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """JSON-выгрузка совпадает с данными сессии из API"""
    token = await _register_and_login(client, "expjson")
    session = await _session_with_dialog(client, token)

    exported = await client.get(
        f"/api/v1/chat/sessions/{session['id']}/export?format=json",
        headers=_auth(token),
    )
    detail = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )

    assert exported.status_code == 200, exported.text
    assert "application/json" in exported.headers["content-type"]
    payload = json.loads(exported.text)
    assert payload == detail.json()
    assert payload["messages"][0]["role"] == "user"


async def test_export_of_foreign_session_forbidden(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Чужую сессию выгрузить нельзя (403)"""
    owner_token = await _register_and_login(client, "expowner")
    session = await _session_with_dialog(client, owner_token)
    other_token = await _register_and_login(client, "expother")

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}/export?format=md",
        headers=_auth(other_token),
    )

    assert response.status_code == 403


async def test_export_unknown_session_returns_404(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Несуществующая сессия — 404"""
    token = await _register_and_login(client, "exp404")

    response = await client.get(
        "/api/v1/chat/sessions/77777777-7777-7777-7777-777777777777/export",
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_settings_are_saved_and_cleared(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Выбранный шаблон промпта сохраняется в users.settings (S43-004)"""
    token = await _register_and_login(client, "settingsuser")

    updated = await client.patch(
        "/api/v1/users/me/settings",
        json={"prompt_template": "explain_code"},
        headers=_auth(token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["settings"]["prompt_template"] == "explain_code"

    profile = await client.get("/api/v1/users/me", headers=_auth(token))
    assert profile.json()["settings"]["prompt_template"] == "explain_code"

    cleared = await client.patch(
        "/api/v1/users/me/settings",
        json={"prompt_template": None},
        headers=_auth(token),
    )
    assert cleared.status_code == 200, cleared.text
    assert "prompt_template" not in cleared.json()["settings"]


async def test_settings_update_rejects_long_value(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Слишком длинный id шаблона — 422"""
    token = await _register_and_login(client, "settingslong")

    response = await client.patch(
        "/api/v1/users/me/settings",
        json={"prompt_template": "x" * 65},
        headers=_auth(token),
    )

    assert response.status_code == 422
