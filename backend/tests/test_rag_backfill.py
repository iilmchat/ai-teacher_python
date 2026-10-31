"""Тесты спринта 27: backfill, порог релевантности, precision (S27-001/002)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.user import User
from app.services.backfill import backfill_embeddings, count_without_embedding
from app.services.llm.embeddings import EmbeddingError, EmbeddingProvider
from app.services.rag import search_chat_messages

FIXTURES = Path(__file__).parent / "fixtures" / "rag_queries.json"


class FakeEmbedding(EmbeddingProvider):
    """Детерминированные векторы: тема → ось (как в test_rag_search)"""

    name = "fake-embed"
    model = "fake"

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_after = fail_after

    async def embed(self, text: str) -> list[float]:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise EmbeddingError("limit reached")
        self.calls.append(text)
        lower = text.lower()
        vector = [0.0] * settings.rag_embedding_dim
        if "кошк" in lower:
            vector[0] = 1.0
        elif "собак" in lower:
            vector[1] = 1.0
        elif "список" in lower:
            vector[2] = 1.0
        else:
            vector[3] = 1.0
        return vector


async def _user(db: AsyncSession, username: str) -> User:
    user = User(
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.commit()
    return user


async def _seed(db: AsyncSession, user_id: Any, texts: list[str]) -> list[ChatMessage]:
    session = ChatSession(user_id=user_id, level="basic")
    db.add(session)
    await db.flush()
    messages = [
        ChatMessage(session_id=session.id, role=MessageRole.USER, content=text)
        for text in texts
    ]
    db.add_all(messages)
    await db.commit()
    return messages


# --- S27-001: backfill ------------------------------------------------------


async def test_backfill_fills_missing_embeddings(
    db_session: AsyncSession
) -> None:
    user = await _user(db_session, "bf_user")
    messages = await _seed(
        db_session, user.id, ["Как перебрать список?", "Что такое кошка?"]
    )
    assert await count_without_embedding(db_session) == len(messages)
    provider = FakeEmbedding()

    stats = await backfill_embeddings(db_session, provider, batch_size=10)

    assert stats["updated"] == len(messages)
    assert stats["errors"] == 0
    assert stats["remaining"] == 0


async def test_backfill_is_idempotent(
    db_session: AsyncSession
) -> None:
    user = await _user(db_session, "bf_user2")
    await _seed(db_session, user.id, ["Как перебрать список?"])

    first = await backfill_embeddings(db_session, FakeEmbedding())
    second = await backfill_embeddings(db_session, FakeEmbedding())

    assert first["updated"] == 1
    assert second["scanned"] == 0
    assert second["updated"] == 0


async def test_backfill_dry_run_writes_nothing(
    db_session: AsyncSession
) -> None:
    user = await _user(db_session, "bf_user3")
    await _seed(db_session, user.id, ["Кошка и собака"])

    stats = await backfill_embeddings(db_session, FakeEmbedding(), dry_run=True)

    assert stats["updated"] == 1
    assert stats["remaining"] == 1


async def test_backfill_continues_after_provider_error(
    db_session: AsyncSession
) -> None:
    user = await _user(db_session, "bf_user4")
    await _seed(db_session, user.id, ["Кошка", "Собака"])

    stats = await backfill_embeddings(
        db_session, FakeEmbedding(fail_after=1), batch_size=10
    )

    assert stats["errors"] >= 1
    assert stats["updated"] >= 1
    assert stats["remaining"] >= 1


async def test_backfill_limit_stops_early(
    db_session: AsyncSession
) -> None:
    user = await _user(db_session, "bf_user5")
    await _seed(db_session, user.id, ["Кошка", "Собака", "Список"])

    stats = await backfill_embeddings(db_session, FakeEmbedding(), limit=2)

    assert stats["scanned"] == 2
    assert stats["remaining"] == 1


# --- S27-002: порог релевантности ------------------------------------------


async def test_min_score_filters_weak_hits_and_falls_back(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "score_user")
    messages = await _seed(db_session, user.id, ["Кошка спит", "Собака лает"])
    provider = FakeEmbedding()
    await backfill_embeddings(db_session, provider)

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_min_score", 0.9)

    # «Собака» встраивается в ось e1: ближайшее — сообщение про собаку (score≈1)
    mode, hits = await search_chat_messages(
        db_session, user.id, "собака", 5, provider
    )

    assert mode == "semantic"
    assert hits
    assert hits[0].message.id == messages[1].id


async def test_min_score_zero_keeps_all(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "score_user2")
    await _seed(db_session, user.id, ["Кошка спит"])
    provider = FakeEmbedding()
    await backfill_embeddings(db_session, provider)

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_min_score", 0.0)

    mode, hits = await search_chat_messages(
        db_session, user.id, "собака", 5, provider
    )

    assert mode == "semantic"
    assert len(hits) >= 1


# --- precision@k на фикстурах ------------------------------------------------


async def test_precision_on_fixture_queries(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    queries: list[dict[str, Any]] = json.loads(FIXTURES.read_text(encoding="utf-8"))
    user = await _user(db_session, "precision_user")
    texts = [item["text"] for query in queries for item in query["messages"]]
    messages = await _seed(db_session, user.id, texts)
    provider = FakeEmbedding()
    await backfill_embeddings(db_session, provider, batch_size=50)

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_min_score", 0.0)

    for query in queries:
        mode, hits = await search_chat_messages(
            db_session, user.id, query["query"], query["k"], provider
        )
        assert mode == "semantic"
        returned_ids = {str(hit.message.id) for hit in hits}
        expected_ids = {
            str(message.id)
            for message in messages
            if any(
                message.content == item["text"]
                for item in query["messages"]
                if item["expected"]
            )
        }
        precision = (
            len(returned_ids & expected_ids) / len(returned_ids) if returned_ids else 0.0
        )
        assert precision >= query["min_precision"], (
            f"query={query['query']} precision={precision} "
            f"returned={returned_ids} expected={expected_ids}"
        )
