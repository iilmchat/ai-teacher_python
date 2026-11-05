"""
Тесты чат-сервиса и Chat API (S4-007).

LLM подменяется фейковым провайдером: тесты не ходят в сеть (RULES §4.4).
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskDifficulty
from app.services.llm.base import LLMMessage
from app.services.llm.prompt_builder import load_system_prompt
from tests.fake_llm import FakeProvider, install_fake_provider, uninstall_fake_provider

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture
def fake_provider() -> Iterator[FakeProvider]:
    """Фейковый LLM-провайдер и его установка в приложение"""
    provider = FakeProvider()
    install_fake_provider(provider)
    yield provider
    uninstall_fake_provider()


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


async def _make_task(db: AsyncSession) -> Task:
    """Задача с маркерами, которых не должно быть в контексте (S42-006)."""
    task = Task(
        title="Сумма через цикл",
        description="Посчитайте сумму чисел от 1 до N и выведите её.",
        difficulty=TaskDifficulty.EASY,
        category="loops",
        tags=["loops"],
        test_cases=[
            {
                "input": "3\n",
                "expected_output": "EXPECTED_OUTPUT_SECRET",
                "description": "Три шага",
            }
        ],
        hints=["HINT_SECRET"],
        solution_template="SOLUTION_SECRET = 1",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


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


async def test_first_message_sets_auto_title(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Первое сообщение задаёт заголовок сессии; второе его не меняет (S43-001)"""
    token = await _register_and_login(client, username="autotitle")
    session = await _create_session(client, token)
    assert session["title"] is None
    assert session["pinned"] is False

    first = "  Почему   мой код " + "не работает? " * 20
    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": first},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text

    listed = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    title = listed.json()[0]["title"]
    assert title.startswith("Почему мой код не работает?")
    assert len(title) <= 60

    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Второй вопрос"},
        headers=_auth(token),
    )
    listed_again = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert listed_again.json()[0]["title"] == title


async def test_rename_session(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Переименование сессии сохраняется и возвращается в детали (S43-001)"""
    token = await _register_and_login(client, username="renamer")
    session = await _create_session(client, token)

    response = await client.patch(
        f"/api/v1/chat/sessions/{session['id']}",
        json={"title": "  Мой разбор задачи  "},
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Мой разбор задачи"
    detail = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )
    assert detail.json()["title"] == "Мой разбор задачи"


async def test_pinned_sessions_go_first(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Закреплённая сессия поднимается над более свежими (S43-001)"""
    token = await _register_and_login(client, username="pinner")
    older = await _create_session(client, token)
    newer = await _create_session(client, token)

    pinned = await client.patch(
        f"/api/v1/chat/sessions/{older['id']}",
        json={"pinned": True},
        headers=_auth(token),
    )
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["pinned"] is True

    listed = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert [item["id"] for item in listed.json()][:2] == [older["id"], newer["id"]]

    unpinned = await client.patch(
        f"/api/v1/chat/sessions/{older['id']}",
        json={"pinned": False},
        headers=_auth(token),
    )
    assert unpinned.json()["pinned"] is False
    listed_again = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert [item["id"] for item in listed_again.json()][:2] == [
        newer["id"],
        older["id"],
    ]


async def test_message_updates_session_order(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Новое сообщение поднимает сессию в списке по updated_at (S43-001)"""
    token = await _register_and_login(client, username="updatedorder")
    first = await _create_session(client, token)
    second = await _create_session(client, token)

    await client.post(
        f"/api/v1/chat/sessions/{first['id']}/messages",
        json={"content": "Сообщение в старую сессию"},
        headers=_auth(token),
    )

    listed = await client.get("/api/v1/chat/sessions", headers=_auth(token))
    assert listed.json()[0]["id"] == first["id"]
    assert listed.json()[1]["id"] == second["id"]


async def test_invalid_session_update_rejected(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Пустой заголовок и запрос без полей отклоняются (422, S43-001)"""
    token = await _register_and_login(client, username="badtitles")
    session = await _create_session(client, token)
    url = f"/api/v1/chat/sessions/{session['id']}"

    empty = await client.patch(url, json={"title": "   "}, headers=_auth(token))
    missing = await client.patch(url, json={}, headers=_auth(token))
    too_long = await client.patch(
        url, json={"title": "x" * 121}, headers=_auth(token)
    )

    assert empty.status_code == 422
    assert missing.status_code == 422
    assert too_long.status_code == 422


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
    patch_response = await client.patch(
        f"/api/v1/chat/sessions/{session['id']}",
        json={"title": "чужой заголовок"},
        headers=_auth(other_token),
    )
    regenerate_response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages/{uuid4()}/regenerate",
        headers=_auth(other_token),
    )

    assert get_response.status_code == 403
    assert post_response.status_code == 403
    assert delete_response.status_code == 403
    assert patch_response.status_code == 403
    assert regenerate_response.status_code == 403


async def test_regenerate_creates_new_answer_and_marks_old_replaced(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Регенерация ответа не дублирует вопрос, старый ответ помечен (S43-002)"""
    token = await _register_and_login(client, username="regen")
    session = await _create_session(client, token)
    sent = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Почему цикл не завершается?"},
        headers=_auth(token),
    )
    assert sent.status_code == 201, sent.text
    old_answer = sent.json()["assistant_message"]

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages/{old_answer['id']}/regenerate",
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    new_answer = response.json()
    assert new_answer["id"] != old_answer["id"]
    assert new_answer["role"] == "assistant"

    detail = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )
    messages = detail.json()["messages"]
    questions = [item for item in messages if item["role"] == "user"]
    answers = [item for item in messages if item["role"] == "assistant"]
    # Вопрос остался один — регенерация его не дублирует.
    assert len(questions) == 1
    assert len(answers) == 2
    replaced = next(item for item in answers if item["id"] == old_answer["id"])
    assert replaced["metadata"]["replaced"] is True
    assert replaced["metadata"]["replaced_by"] == new_answer["id"]


async def test_regenerate_rejects_user_message(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Регенерировать можно только ответ ассистента (422)"""
    token = await _register_and_login(client, username="regenuser")
    session = await _create_session(client, token)
    sent = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Вопрос ученика"},
        headers=_auth(token),
    )
    question = sent.json()["user_message"]

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages/{question['id']}/regenerate",
        headers=_auth(token),
    )

    assert response.status_code == 422


async def test_regenerate_unknown_message_returns_404(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Несуществующее сообщение — 404"""
    token = await _register_and_login(client, username="regen404")
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages/{uuid4()}/regenerate",
        headers=_auth(token),
    )

    assert response.status_code == 404


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


async def test_task_context_in_metadata_not_content(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Контекст задачи — в метаданных, а не в тексте сообщения (S42-006)."""
    task = await _make_task(db_session)
    token = await _register_and_login(client, username="taskmeta")
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Объясни условие", "task_id": str(task.id)},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    user_message = response.json()["user_message"]
    assert user_message["content"] == "Объясни условие"
    assert "Сумма через цикл" not in user_message["content"]
    assert user_message["metadata"] == {
        "task_context": {"task_id": str(task.id), "title": "Сумма через цикл"}
    }


async def test_task_context_sent_to_llm_without_solution(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """Условие уходит вторым системным сообщением, без решения и ответов."""
    task = await _make_task(db_session)
    token = await _register_and_login(client, username="taskprompt")
    session = await _create_session(client, token)

    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "С чего начать?", "task_id": str(task.id)},
        headers=_auth(token),
    )

    messages = fake_provider.calls[0]
    assert messages[0].role == "system"
    assert messages[1].role == "system"
    context = messages[1].content
    assert "Сумма через цикл" in context
    assert "Посчитайте сумму чисел" in context
    assert "Три шага" in context
    # Эталонное решение, ожидаемые выводы и подсказки не передаются
    assert "SOLUTION_SECRET" not in context
    assert "EXPECTED_OUTPUT_SECRET" not in context
    assert "HINT_SECRET" not in context
    assert messages[-1] == LLMMessage(role="user", content="С чего начать?")


async def test_task_context_not_leaked_into_history(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    """В истории остаётся вопрос, а контекст — только в метаданных."""
    task = await _make_task(db_session)
    token = await _register_and_login(client, username="taskhistory")
    session = await _create_session(client, token)

    await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Подскажи идею", "task_id": str(task.id)},
        headers=_auth(token),
    )

    response = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )
    user_message = response.json()["messages"][0]
    assert user_message["content"] == "Подскажи идею"
    assert "Посчитайте сумму чисел" not in user_message["content"]
    assert user_message["metadata"]["task_context"]["task_id"] == str(task.id)


async def test_unknown_task_context_returns_404(
    client: AsyncClient, fake_provider: FakeProvider
) -> None:
    """Несуществующая задача не подменяется пустым контекстом."""
    token = await _register_and_login(client, username="taskmissing")
    session = await _create_session(client, token)

    response = await client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        json={"content": "Вопрос", "task_id": str(uuid4())},
        headers=_auth(token),
    )

    assert response.status_code == 404
    history = await client.get(
        f"/api/v1/chat/sessions/{session['id']}", headers=_auth(token)
    )
    assert history.json()["messages"] == []
    assert fake_provider.calls == []
