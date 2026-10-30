"""
Тесты RAG-lite: поиск по истории чата (S19-005).

Провайдер эмбеддингов и LLM подменяются фейками — тесты не ходят в сеть.
Проверяются: семантический режим, ILIKE-fallback, изоляция чужих сессий и
fail-open при сбоях провайдера.
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.chat import ChatMessage, MessageRole
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    create_embedding_provider,
)
from tests.task_helpers import auth

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
SEARCH_URL = "/api/v1/chat/search"


class FakeLLM(LLMProvider):
    """Фейковый LLM: фиксированный ответ без ключевых слов запроса"""

    name = "fake"
    reply = "Давай разберёмся по шагам."

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield self.reply


class FakeEmbedding(EmbeddingProvider):
    """Детерминированные векторы: «кошка» → e0, «собака» → e1, иначе → e2"""

    name = "fake-embed"
    model = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.fail:
            raise EmbeddingError("provider is down")
        lower = text.lower()
        vector = [0.0] * settings.rag_embedding_dim
        if "кошк" in lower:
            vector[0] = 1.0
        elif "собак" in lower:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector


@pytest.fixture
def fake_llm() -> Iterator[None]:
    """Подменить LLM-провайдер в приложении"""
    from app.api.v1.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM()
    yield
    app.dependency_overrides.pop(get_llm_provider, None)


@pytest.fixture
def fake_embedding() -> Iterator[FakeEmbedding]:
    """Подменить провайдер эмбеддингов валидным фейком"""
    from app.api.v1.chat import get_embedding_provider

    provider = FakeEmbedding()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.fixture
def failing_embedding() -> Iterator[FakeEmbedding]:
    """Подменить провайдер эмбеддингов падающим фейком"""
    from app.api.v1.chat import get_embedding_provider

    provider = FakeEmbedding(fail=True)
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_embedding_provider, None)


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


async def _session(client: AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/chat/sessions", json={}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _send(client: AsyncClient, token: str, session_id: str, text: str) -> None:
    response = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": text},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text


async def _search(
    client: AsyncClient, token: str, query: str, **params: Any
) -> dict[str, Any]:
    response = await client.get(
        SEARCH_URL, params={"q": query, **params}, headers=auth(token)
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_ilike_fallback_when_rag_disabled(
    client: AsyncClient, fake_llm: None
) -> None:
    """RAG_ENABLED=false → поиск по подстроке, режим ilike"""
    token = await _register_and_login(client, "ragstudent")
    session = await _session(client, token)
    await _send(client, token, session["id"], "Расскажи про кошку")

    data = await _search(client, token, "кошку")

    assert data["mode"] == "ilike"
    assert data["total"] == 1
    assert "кошку" in data["items"][0]["content"]
    assert data["items"][0]["score"] is None


async def test_semantic_search_ranks_best_match(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_llm: None,
    fake_embedding: FakeEmbedding,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RAG_ENABLED=true → семантический поиск по pgvector, лучший матч первый"""
    monkeypatch.setattr(settings, "rag_enabled", True)
    token = await _register_and_login(client, "ragsemantic")
    session = await _session(client, token)
    await _send(client, token, session["id"], "Расскажи про кошку")
    await _send(client, token, session["id"], "Расскажи про собаку")

    rows = (
        await db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.role == MessageRole.USER)
            .order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    assert all(row.embedding is not None for row in rows)

    data = await _search(client, token, "кошка")

    assert data["mode"] == "semantic"
    assert data["items"][0]["content"] == "Расскажи про кошку"
    assert data["items"][0]["score"] is not None
    assert data["items"][0]["score"] > 0.9


async def test_semantic_search_isolated_to_own_sessions(
    client: AsyncClient,
    fake_llm: None,
    fake_embedding: FakeEmbedding,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Семантический поиск не видит чужих сообщений: только свои сессии"""
    monkeypatch.setattr(settings, "rag_enabled", True)
    owner = await _register_and_login(client, "ragowner")
    owner_session = await _session(client, owner)
    await _send(client, owner, owner_session["id"], "секретная кошка")

    other = await _register_and_login(client, "ragother")
    other_session = await _session(client, other)
    await _send(client, other, other_session["id"], "моя собака")

    data = await _search(client, other, "кошка")

    assert data["total"] >= 1
    assert all(item["session_id"] == other_session["id"] for item in data["items"])
    assert all("секретная кошка" not in item["content"] for item in data["items"])


async def test_ilike_search_isolated_to_own_sessions(
    client: AsyncClient, fake_llm: None
) -> None:
    """ILIKE-поиск не видит чужих сообщений (фильтр по user_id в SQL)"""
    owner = await _register_and_login(client, "ilikeowner")
    owner_session = await _session(client, owner)
    await _send(client, owner, owner_session["id"], "секретная кошка")

    other = await _register_and_login(client, "ilikeother")
    other_session = await _session(client, other)
    await _send(client, other, other_session["id"], "моя собака")

    own = await _search(client, other, "секретная")
    foreign = await _search(client, owner, "секретная")

    assert own["total"] == 0
    assert foreign["total"] == 1
    assert foreign["items"][0]["session_id"] == owner_session["id"]


async def test_search_requires_auth(client: AsyncClient) -> None:
    """Без токена поиск недоступен"""
    response = await client.get(SEARCH_URL, params={"q": "кошка"})

    assert response.status_code in (401, 403)


async def test_search_and_session_isolation_403_404(
    client: AsyncClient, fake_llm: None
) -> None:
    """Поиск отдаёт только свои сессии: чужая — 403, несуществующая — 404"""
    owner = await _register_and_login(client, "isolationowner")
    owner_session = await _session(client, owner)
    await _send(client, owner, owner_session["id"], "секретная кошка")

    other = await _register_and_login(client, "isolationother")
    other_session = await _session(client, other)

    foreign = await client.get(
        f"/api/v1/chat/sessions/{owner_session['id']}", headers=auth(other)
    )
    missing = await client.get(
        "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
        headers=auth(other),
    )
    search = await _search(client, other, "кошка")

    assert foreign.status_code == 403
    assert missing.status_code == 404
    # Выдача поиска ограничена сессиями самого пользователя
    assert all(
        item["session_id"] == other_session["id"] for item in search["items"]
    )


async def test_empty_query_rejected(client: AsyncClient, fake_llm: None) -> None:
    """Пустой запрос отклоняется схемой (422)"""
    token = await _register_and_login(client, "ragempty")

    response = await client.get(SEARCH_URL, params={"q": ""}, headers=auth(token))

    assert response.status_code == 422


async def test_search_limit_is_respected(
    client: AsyncClient, fake_llm: None
) -> None:
    """limit ограничивает выдачу; значения вне диапазона — 422"""
    token = await _register_and_login(client, "raglimit")
    session = await _session(client, token)
    for index in range(3):
        await _send(client, token, session["id"], f"яблоко {index}")

    data = await _search(client, token, "яблоко", limit=1)

    assert data["total"] == 1

    invalid = await client.get(
        SEARCH_URL, params={"q": "яблоко", "limit": 0}, headers=auth(token)
    )
    assert invalid.status_code == 422


async def test_embedding_failure_does_not_break_message_send(
    client: AsyncClient, db_session: AsyncSession, fake_llm: None,
    failing_embedding: FakeEmbedding, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сбой провайдера эмбеддингов: сообщение сохраняется, вектор не пишется"""
    monkeypatch.setattr(settings, "rag_enabled", True)
    token = await _register_and_login(client, "ragfail")
    session = await _session(client, token)

    await _send(client, token, session["id"], "кошка идёт по крыше")

    row = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.content == "кошка идёт по крыше")
        )
    ).scalar_one()
    assert row.embedding is None
    assert failing_embedding.calls


async def test_search_falls_back_to_ilike_on_embedding_failure(
    client: AsyncClient, fake_llm: None,
    failing_embedding: FakeEmbedding, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Если провайдер эмбеддингов упал на поиске — выдаётся ILIKE-результат"""
    monkeypatch.setattr(settings, "rag_enabled", True)
    token = await _register_and_login(client, "ragfallback")
    session = await _session(client, token)
    await _send(client, token, session["id"], "кошка идёт по крыше")

    data = await _search(client, token, "кошка")

    assert data["mode"] == "ilike"
    assert data["total"] == 1
    assert "кошка" in data["items"][0]["content"]


async def test_embedding_provider_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Фабрика эмбеддингов: None при выключенном RAG, провайдер при включённом"""
    monkeypatch.setattr(settings, "rag_enabled", False)
    assert create_embedding_provider() is None

    monkeypatch.setattr(settings, "rag_enabled", True)
    provider = create_embedding_provider()
    assert provider is not None
    assert provider.name == "lm_studio"
    await provider.close()
