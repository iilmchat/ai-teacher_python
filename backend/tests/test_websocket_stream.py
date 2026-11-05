"""
Тесты протокола WebSocket-стриминга (S11-004, S43-002, закрывает KI-006).

Сокет подменяется фейком: проверяем последовательность сообщений, сохранение
ответа в БД и устойчивость к ошибкам провайдера — без реальной сети.
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import serve_chat_socket
from app.models.chat import ChatSession
from app.models.task import Task, TaskDifficulty
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.llm.base import LLMMessage, LLMProvider, LLMUnavailableError


class FakeSocket:
    """Сокет с очередью входящих и записью исходящих сообщений"""

    def __init__(self, incoming: list[dict[str, Any]] | list[str]) -> None:
        self.incoming = [
            item if isinstance(item, str) else json.dumps(item) for item in incoming
        ]
        self.sent: list[dict[str, Any]] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def receive_text(self) -> str:
        if not self.incoming:
            raise WebSocketDisconnect()
        return self.incoming.pop(0)

    def types(self) -> list[str]:
        return [item["type"] for item in self.sent]


class QueueSocket:
    """Сокет с очередью: сообщения можно досылать во время стрима (S43-002)"""

    def __init__(self) -> None:
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.sent: list[dict[str, Any]] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def receive_text(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise WebSocketDisconnect()
        return item

    async def push(self, payload: dict[str, Any]) -> None:
        await self.incoming.put(json.dumps(payload))

    def disconnect(self) -> None:
        self.incoming.put_nowait(None)

    def types(self) -> list[str]:
        return [item["type"] for item in self.sent]


class StreamingProvider(LLMProvider):
    """Провайдер, отдающий заранее заданные дельты"""

    name = "fake"

    def __init__(self, deltas: list[str] | None = None, fail: bool = False) -> None:
        self.deltas = deltas or ["Попробуй ", "проверить условие."]
        self.fail = fail
        self.calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return "".join(self.deltas)

    async def stream(  # type: ignore[override]
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        if self.fail:
            raise LLMUnavailableError("DeepSeek недоступен: timeout")
        self.calls.append(messages)
        for delta in self.deltas:
            yield delta


class SlowStreamingProvider(StreamingProvider):
    """Провайдер с паузой между дельтами — поток можно остановить (S43-002)"""

    async def stream(  # type: ignore[override]
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.calls.append(messages)
        for delta in self.deltas:
            await asyncio.sleep(0.05)
            yield delta


async def _make_session(db: AsyncSession, user: User) -> ChatSession:
    session = ChatSession(user_id=user.id, level="basic")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _make_task(db: AsyncSession) -> Task:
    """Задача для проверки контекста в сокете (S42-006)."""
    task = Task(
        title="Сумма через цикл",
        description="Посчитайте сумму чисел от 1 до N.",
        difficulty=TaskDifficulty.EASY,
        category="loops",
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


async def _make_user(db: AsyncSession, username: str = "wsuser") -> User:
    from app.core.security import hash_password

    user = User(
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_stream_sends_start_tokens_done(db_session: AsyncSession) -> None:
    """Полный цикл: start → token… → done, ответ сохранён"""
    user = await _make_user(db_session)
    session = await _make_session(db_session, user)
    provider = StreamingProvider()
    service = ChatService(db_session, provider)
    socket = FakeSocket([{"type": "chat", "content": "Как работает цикл?"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["start", "token", "token", "done"]
    assert socket.sent[-1]["content"] == "Попробуй проверить условие."

    history = await service.get_history(session.id)
    assert [message.role.value for message in history] == ["user", "assistant"]
    assert history[-1].content == "Попробуй проверить условие."


async def test_ping_returns_pong(db_session: AsyncSession) -> None:
    """ping → pong"""
    user = await _make_user(db_session, "wsping")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket([{"type": "ping"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.sent == [{"type": "pong"}]


async def test_invalid_json_reports_error(db_session: AsyncSession) -> None:
    """Не-JSON не роняет соединение"""
    user = await _make_user(db_session, "wsjson")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket(["not-json", {"type": "ping"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["error", "pong"]


async def test_unknown_type_reports_error(db_session: AsyncSession) -> None:
    """Неизвестный тип сообщения — error, соединение живо"""
    user = await _make_user(db_session, "wsunknown")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket([{"type": "subscribe"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["error"]


async def test_provider_failure_reports_error_and_keeps_alive(
    db_session: AsyncSession,
) -> None:
    """Ошибка провайдера: error вместо done, соединение не закрывается"""
    user = await _make_user(db_session, "wsfail")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider(fail=True))
    socket = FakeSocket([{"type": "chat", "content": "вопрос"}, {"type": "ping"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    # Генерация идёт в отдельной задаче (S43-002), поэтому ping отвечает
    # раньше, чем придёт ошибка стрима.
    assert socket.types()[0] == "start"
    assert set(socket.types()) == {"start", "pong", "error"}
    assert "недоступен" in socket.sent[-1]["detail"]


async def test_done_reports_level_policy_warnings(db_session: AsyncSession) -> None:
    """Готовое решение на базовом уровне приходит с warnings (S12-005)"""
    user = await _make_user(db_session, "wswarn")
    session = await _make_session(db_session, user)
    code = (
        "n = int(input())\n"
        "total = 0\n"
        "for i in range(1, n + 1):\n"
        "    total += i\n"
        "print(total)"
    )
    provider = StreamingProvider(deltas=[f"```python\n{code}\n```"])
    service = ChatService(db_session, provider)
    socket = FakeSocket([{"type": "chat", "content": "Напиши программу"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    done = socket.sent[-1]
    assert done["type"] == "done"
    assert "basic_full_solution" in done["warnings"]


async def test_task_context_is_passed_to_stream(
    db_session: AsyncSession,
) -> None:
    """task_id из сокета добавляет условие системным сообщением (S42-006)"""
    user = await _make_user(db_session, "wstask")
    session = await _make_session(db_session, user)
    task = await _make_task(db_session)
    provider = StreamingProvider()
    service = ChatService(db_session, provider)
    socket = FakeSocket(
        [
            {
                "type": "chat",
                "content": "С чего начать?",
                "task_id": str(task.id),
            }
        ]
    )

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["start", "token", "token", "done"]
    messages = provider.calls[0]
    assert messages[1].role == "system"
    assert "Сумма через цикл" in messages[1].content
    assert "SOLUTION_SECRET" not in messages[1].content
    assert "EXPECTED_OUTPUT_SECRET" not in messages[1].content

    history = await service.get_history(session.id)
    assert history[0].content == "С чего начать?"
    assert history[0].message_metadata == {
        "task_context": {"task_id": str(task.id), "title": "Сумма через цикл"}
    }


async def test_invalid_task_id_reports_error(db_session: AsyncSession) -> None:
    """Невалидный task_id — error, соединение остаётся живым (S42-006)"""
    user = await _make_user(db_session, "wsbadid")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket(
        [{"type": "chat", "content": "вопрос", "task_id": "not-a-uuid"}, {"type": "ping"}]
    )

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["error", "pong"]
    assert await service.get_history(session.id) == []


async def test_unknown_task_id_reports_error(db_session: AsyncSession) -> None:
    """Несуществующая задача не сохраняет сообщение с пустым контекстом"""
    user = await _make_user(db_session, "wsmissing")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket(
        [
            {"type": "chat", "content": "вопрос", "task_id": str(uuid4())},
            {"type": "ping"},
        ]
    )

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types()[0] == "start"
    assert set(socket.types()) == {"start", "pong", "error"}
    assert socket.sent[-1]["detail"] == "Задача не найдена"
    assert await service.get_history(session.id) == []


async def test_stop_interrupts_stream_and_saves_partial(
    db_session: AsyncSession,
) -> None:
    """Команда `stop` прерывает генерацию, частичный ответ сохраняется (S43-002)"""
    user = await _make_user(db_session, "wsstop")
    session = await _make_session(db_session, user)
    provider = SlowStreamingProvider(
        deltas=["Первая часть ", "вторая часть ", "третья часть."]
    )
    service = ChatService(db_session, provider)
    socket = QueueSocket()

    task = asyncio.create_task(serve_chat_socket(socket, service, session))
    await socket.push({"type": "chat", "content": "Долгий ответ"})

    # Ждём первый токен — до этого останавливать нечего.
    for _ in range(200):
        if "token" in socket.types():
            break
        await asyncio.sleep(0.01)
    assert "token" in socket.types()

    await socket.push({"type": "stop"})
    socket.disconnect()

    with pytest.raises(WebSocketDisconnect):
        await asyncio.wait_for(task, timeout=10)

    assert socket.types()[-1] == "stopped"

    history = await service.get_history(session.id)
    answers = [message for message in history if message.role.value == "assistant"]
    assert len(answers) == 1
    assert answers[0].message_metadata.get("stopped") is True
    assert answers[0].content.startswith("Первая часть")
    assert len(answers[0].content) < len("Первая часть вторая часть третья часть.")


async def test_stop_without_active_stream_is_safe(
    db_session: AsyncSession,
) -> None:
    """`stop` без запущенной генерации не ломает соединение (S43-002)"""
    user = await _make_user(db_session, "wsstopidle")
    session = await _make_session(db_session, user)
    service = ChatService(db_session, StreamingProvider())
    socket = FakeSocket([{"type": "stop"}, {"type": "ping"}])

    with pytest.raises(WebSocketDisconnect):
        await serve_chat_socket(socket, service, session)

    assert socket.types() == ["pong"]
    assert await service.get_history(session.id) == []
