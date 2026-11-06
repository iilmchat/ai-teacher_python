"""Личные сниппеты кода в `users.settings` (S44-003)."""

from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
SETTINGS_URL = "/api/v1/users/me/settings"


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _snippet(index: int) -> dict[str, str]:
    return {
        "id": f"snippet-{index}",
        "name": f"Сниппет {index}",
        "code": f"print({index})",
    }


async def test_snippets_are_saved_and_read_back(client: AsyncClient) -> None:
    """Список сниппетов сохраняется в settings и возвращается в профиле"""
    token = await _register_and_login(client, "snippetsave")
    snippets = [_snippet(1), _snippet(2)]

    updated = await client.patch(
        SETTINGS_URL, json={"snippets": snippets}, headers=_auth(token)
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["settings"]["snippets"] == snippets

    profile = await client.get("/api/v1/users/me", headers=_auth(token))
    assert profile.json()["settings"]["snippets"] == snippets


async def test_snippets_are_cleared(client: AsyncClient) -> None:
    """`null` очищает список сниппетов"""
    token = await _register_and_login(client, "snippetclear")

    await client.patch(
        SETTINGS_URL, json={"snippets": [_snippet(1)]}, headers=_auth(token)
    )
    cleared = await client.patch(
        SETTINGS_URL, json={"snippets": None}, headers=_auth(token)
    )

    assert cleared.status_code == 200, cleared.text
    assert "snippets" not in cleared.json()["settings"]


async def test_snippets_limit_is_twenty(client: AsyncClient) -> None:
    """Больше 20 сниппетов сохранить нельзя"""
    token = await _register_and_login(client, "snippetlimit")
    snippets = [_snippet(index) for index in range(21)]

    response = await client.patch(
        SETTINGS_URL, json={"snippets": snippets}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_duplicate_snippet_ids_are_rejected(client: AsyncClient) -> None:
    """Повторяющиеся id делают удаление неоднозначным — 422"""
    token = await _register_and_login(client, "snippetdupe")
    snippets = [_snippet(1), {**_snippet(2), "id": "snippet-1"}]

    response = await client.patch(
        SETTINGS_URL, json={"snippets": snippets}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_snippet_with_too_long_code_is_rejected(client: AsyncClient) -> None:
    """Код сниппета длиннее лимита песочницы — 422"""
    token = await _register_and_login(client, "snippetlong")
    snippet = {**_snippet(1), "code": "x" * 20_001}

    response = await client.patch(
        SETTINGS_URL, json={"snippets": [snippet]}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_snippets_do_not_replace_prompt_template(client: AsyncClient) -> None:
    """Настройки дополняются: сниппеты не стирают выбранный шаблон"""
    token = await _register_and_login(client, "snippetmerge")

    await client.patch(
        SETTINGS_URL, json={"prompt_template": "explain_code"}, headers=_auth(token)
    )
    updated = await client.patch(
        SETTINGS_URL, json={"snippets": [_snippet(1)]}, headers=_auth(token)
    )

    settings = updated.json()["settings"]
    assert settings["prompt_template"] == "explain_code"
    assert settings["snippets"] == [_snippet(1)]
