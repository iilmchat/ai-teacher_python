"""
Сервис чата (S4-002, S4-004, S5-003, S12-005, S12-006).

Отвечает за сессии, историю сообщений, сборку контекста с учётом уровня
и вызов LLM. Провайдер передаётся снаружи — это делает слой тестируемым
без сети.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.chat import ChatMessageRepository, ChatSessionRepository
from app.errors import AccessDeniedError, NotFoundError, ValidationError
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.user import User, UserLevel
from app.services.levels import resolve_level
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.embeddings import EmbeddingProvider
from app.services.llm.policy import (
    detect_level_policy_violations,
    extract_code_blocks,
)
from app.services.llm.prompt_builder import build_messages, prompt_version
from app.services.rag import (
    SearchHit,
    SearchMode,
    search_chat_messages,
    try_embed,
)

logger = structlog.get_logger(__name__)

__all__ = ["ChatService", "extract_code_blocks", "parse_level"]


def parse_level(value: str | UserLevel) -> UserLevel:
    """Привести уровень к enum, отклонив неизвестные значения"""
    if isinstance(value, UserLevel):
        return value
    try:
        return UserLevel(value)
    except ValueError:
        allowed = ", ".join(level.value for level in UserLevel)
        raise ValidationError(f"Неизвестный уровень '{value}'. Допустимо: {allowed}") from None


class ChatService:
    """Бизнес-логика чата"""

    def __init__(
        self,
        db: AsyncSession,
        provider: LLMProvider,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        #: Провайдер эмбеддингов для RAG-lite (S19-005); ``None`` — RAG выключен
        self.embedding_provider = embedding_provider
        self.sessions = ChatSessionRepository(db)
        self.messages = ChatMessageRepository(db)
        #: Предупреждения политики уровня для последнего ответа (S12-005)
        self.last_warnings: list[str] = []

    # --- Сессии ---------------------------------------------------------

    async def create_session(
        self, user: User, level: str | UserLevel | None = None
    ) -> ChatSession:
        """Создать сессию чата для пользователя.

        Уровень нормализуется и проверяется на наличие промпта (fallback
        на базовый уровень из S5-003).
        """
        requested = parse_level(level or user.level)
        session = ChatSession(
            user_id=user.id,
            level=resolve_level(requested).value,
        )
        return await self.sessions.create(session)

    async def list_sessions(
        self, user: User, skip: int = 0, limit: int = 100
    ) -> list[ChatSession]:
        """Все сессии пользователя (новые сверху)"""
        return await self.sessions.get_user_sessions(user.id, skip=skip, limit=limit)

    async def get_session(
        self, session_id: UUID, user: User, with_messages: bool = False
    ) -> ChatSession:
        """Получить сессию с проверкой владельца"""
        session = (
            await self.sessions.get_with_messages(session_id)
            if with_messages
            else await self.sessions.get(session_id)
        )
        if session is None:
            raise NotFoundError("Сессия чата не найдена")
        if session.user_id != user.id:
            raise AccessDeniedError("Сессия принадлежит другому пользователю")
        return session

    async def delete_session(self, session_id: UUID, user: User) -> None:
        """Удалить сессию с проверкой владельца"""
        await self.get_session(session_id, user)
        await self.sessions.delete(session_id)

    async def get_history(self, session_id: UUID) -> list[ChatMessage]:
        """Сообщения сессии в хронологическом порядке"""
        return await self.messages.get_session_messages(session_id)

    async def search(
        self, user: User, query: str, limit: int
    ) -> tuple[SearchMode, list[SearchHit]]:
        """Поиск по своим сообщениям: semantic при RAG, иначе ILIKE (S19-005)"""
        return await search_chat_messages(
            self.db, user.id, query, limit, self.embedding_provider
        )

    # --- Сообщения ------------------------------------------------------

    def _history_for_llm(self, history: list[ChatMessage]) -> list[LLMMessage]:
        """Преобразовать историю БД в сообщения для LLM.

        Последнее сообщение (текущий вопрос ученика) исключается: его
        добавляет `build_messages`, иначе вопрос попал бы в контекст дважды.
        """
        items = history[:-1] if history else history
        return [
            LLMMessage(role=message.role.value, content=message.content)
            for message in items
        ]

    def _assistant_metadata(self, level: UserLevel, answer: str) -> dict[str, Any]:
        """Метаданные ответа: провайдер, модель, версия промпта, предупреждения"""
        metadata: dict[str, Any] = {
            "provider": self.provider.used_provider,
            "model": self.provider.model,
            "prompt_version": prompt_version(level),
        }
        warnings = detect_level_policy_violations(level, answer)
        self.last_warnings = warnings
        if warnings:
            metadata["warnings"] = warnings
            logger.warning(
                "level_policy_warning",
                level=level.value,
                codes=warnings,
                provider=self.provider.used_provider,
            )
        return metadata

    async def send_message(
        self, session: ChatSession, content: str
    ) -> tuple[ChatMessage, ChatMessage]:
        """Сохранить сообщение ученика и вернуть пару (вопрос, ответ)"""
        text = content.strip()
        if not text:
            raise ValidationError("Сообщение не может быть пустым")

        # RAG-lite: вектор считается best-effort, ошибка не ломает отправку
        user_embedding = await try_embed(self.embedding_provider, text)
        user_message = await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=text,
            embedding=user_embedding,
        )
        # Последнее сообщение истории — только что сохранённый вопрос,
        # его передаём в build_messages отдельно, чтобы не дублировать
        history = await self.get_history(session.id)
        level = resolve_level(parse_level(session.level))
        llm_messages = build_messages(
            level,
            self._history_for_llm(history),
            text,
        )

        answer = await self.provider.generate(llm_messages)
        answer_embedding = await try_embed(self.embedding_provider, answer)
        assistant_message = await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            code_blocks=extract_code_blocks(answer),
            metadata=self._assistant_metadata(level, answer),
            embedding=answer_embedding,
        )
        return user_message, assistant_message

    async def stream_reply(
        self, session: ChatSession, content: str
    ) -> AsyncIterator[str]:
        """Потоковый ответ: сообщение ученика сохраняется сразу,
        ответ ассистента — по завершении потока."""
        text = content.strip()
        if not text:
            raise ValidationError("Сообщение не может быть пустым")

        self.last_warnings = []
        user_embedding = await try_embed(self.embedding_provider, text)
        await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=text,
            embedding=user_embedding,
        )
        history = await self.get_history(session.id)
        level = resolve_level(parse_level(session.level))
        llm_messages = build_messages(
            level,
            self._history_for_llm(history),
            text,
        )

        chunks: list[str] = []
        async for delta in self.provider.stream(llm_messages):
            chunks.append(delta)
            yield delta

        answer = "".join(chunks).strip()
        if answer:
            answer_embedding = await try_embed(self.embedding_provider, answer)
            await self.messages.create_message(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=answer,
                code_blocks=extract_code_blocks(answer),
                metadata=self._assistant_metadata(level, answer),
                embedding=answer_embedding,
            )
