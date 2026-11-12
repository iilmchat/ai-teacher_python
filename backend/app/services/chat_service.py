"""
Сервис чата (S4-002, S4-004, S5-003, S12-005, S12-006, S43-002).

Отвечает за сессии, историю сообщений, сборку контекста с учётом уровня
и вызов LLM. Провайдер передаётся снаружи — это делает слой тестируемым
без сети.
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.repositories.chat import ChatMessageRepository, ChatSessionRepository
from app.db.repositories.task import TaskRepository
from app.errors import AccessDeniedError, NotFoundError, ValidationError
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.task import Task
from app.models.user import User, UserLevel
from app.services.levels import resolve_level
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.embeddings import EmbeddingProvider
from app.services.llm.guardrails import check_user_input
from app.services.llm.policy import (
    detect_level_policy_violations,
    extract_code_blocks,
)
from app.services.llm.prompt_builder import build_messages, prompt_version
from app.services.llm.task_context import (
    build_task_context_message,
    task_context_metadata,
)
from app.services.rag import (
    SearchHit,
    SearchMode,
    search_chat_messages,
    try_embed,
)

logger = structlog.get_logger(__name__)

__all__ = ["ChatService", "build_session_title", "extract_code_blocks", "parse_level"]

#: Сколько символов первого вопроса попадает в авто-заголовок сессии (S43-001)
AUTO_TITLE_CHARS = 60


def build_session_title(content: str) -> str:
    """Заголовок из первого вопроса: одна строка, не длиннее 60 символов."""
    normalized = " ".join(content.split())
    return normalized[:AUTO_TITLE_CHARS].strip()


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

    async def update_session(
        self,
        session_id: UUID,
        user: User,
        title: str | None = None,
        pinned: bool | None = None,
    ) -> ChatSession:
        """Переименовать и/или закрепить сессию (S43-001)."""
        session = await self.get_session(session_id, user)
        if title is not None:
            session.title = title
        if pinned is not None:
            session.pinned = pinned
        # Переименование и закрепление не должны менять порядок «свежие сверху»:
        # `flag_modified` явно пишет updated_at, иначе `onupdate` поднял бы
        # сессию в начало списка.
        flag_modified(session, "updated_at")
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def _remember_user_message(
        self, session: ChatSession, content: str
    ) -> None:
        """Обновить updated_at и, если нужно, авто-заголовок (S43-001)."""
        if not session.title:
            session.title = build_session_title(content)
        await self._touch_session(session)

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

    async def _task_for_context(self, task_id: UUID | None) -> Task | None:
        """Активная задача для контекста чата (S42-006).

        Неизвестный или удалённый идентификатор — 404: контекст не должен
        молча подменяться чужой или несуществующей задачей.
        """
        if task_id is None:
            return None
        task = await TaskRepository(self.db).get(task_id)
        if task is None or not task.is_active:
            raise NotFoundError("Задача не найдена")
        logger.debug(
            "chat_task_context_attached",
            task_id=str(task.id),
        )
        return task

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

    async def _save_assistant_answer(
        self,
        session: ChatSession,
        answer: str,
        level: UserLevel,
        *,
        stopped: bool = False,
    ) -> ChatMessage:
        """Сохранить ответ ассистента (полный или частичный).

        `stopped=True` — ответ прерван учеником (S43-002): в метаданных
        остаётся пометка `stopped`, чтобы интерфейс показал состояние.
        """
        metadata = self._assistant_metadata(level, answer)
        if stopped:
            metadata["stopped"] = True
        embedding = await try_embed(self.embedding_provider, answer)
        message = await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            code_blocks=extract_code_blocks(answer),
            metadata=metadata,
            embedding=embedding,
        )
        await self._touch_session(session)
        return message

    async def save_reply(
        self, session: ChatSession, answer: str, *, stopped: bool = False
    ) -> ChatMessage:
        """Сохранить ответ ассистента, полученный потоком (S43-002).

        Ответ сохраняет вызывающий, а не сам генератор: так частичный ответ
        фиксируется даже при обрыве WebSocket-соединения.
        """
        level = resolve_level(parse_level(session.level))
        return await self._save_assistant_answer(
            session, answer, level, stopped=stopped
        )

    async def _touch_session(self, session: ChatSession) -> None:
        """Обновить `updated_at` сессии (новое сообщение изменило диалог)"""
        session.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(session)

    async def send_message(
        self, session: ChatSession, content: str, task_id: UUID | None = None
    ) -> tuple[ChatMessage, ChatMessage]:
        """Сохранить сообщение ученика и вернуть пару (вопрос, ответ).

        `task_id` (S42-006) добавляет условие задачи отдельным системным
        сообщением; в `content` и в историю попадает только вопрос.
        """
        text = content.strip()
        if not text:
            raise ValidationError("Сообщение не может быть пустым")

        task = await self._task_for_context(task_id)
        task_context = build_task_context_message(task) if task else None
        metadata = task_context_metadata(task) if task else None

        # S38-004: фильтр prompt injection/токсичности до сохранения и LLM.
        guard = check_user_input(text)
        if not guard.allowed:
            raise ValidationError(guard.message)

        # RAG-lite: вектор считается best-effort, ошибка не ломает отправку
        user_embedding = await try_embed(self.embedding_provider, text)
        user_message = await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=text,
            metadata=metadata,
            embedding=user_embedding,
        )
        await self._remember_user_message(session, text)
        # Последнее сообщение истории — только что сохранённый вопрос,
        # его передаём в build_messages отдельно, чтобы не дублировать
        history = await self.get_history(session.id)
        level = resolve_level(parse_level(session.level))
        llm_messages = build_messages(
            level,
            self._history_for_llm(history),
            text,
            task_context=task_context,
        )

        answer = await self.provider.generate(llm_messages)
        assistant_message = await self._save_assistant_answer(session, answer, level)
        return user_message, assistant_message

    async def regenerate_reply(
        self, session: ChatSession, message_id: UUID
    ) -> ChatMessage:
        """Перегенерировать ответ ассистента (S43-002).

        Вопрос ученика не дублируется: LLM получает тот же контекст, что и
        при первом ответе. Прежний ответ остаётся в истории, но помечается в
        `message_metadata` как заменённый (`replaced`, `replaced_by`).
        """
        history = await self.get_history(session.id)
        index = next(
            (position for position, item in enumerate(history) if item.id == message_id),
            None,
        )
        if index is None:
            raise NotFoundError("Сообщение не найдено")
        target = history[index]
        if target.role != MessageRole.ASSISTANT:
            raise ValidationError("Перегенерировать можно только ответ ассистента")

        question = next(
            (
                item
                for item in reversed(history[:index])
                if item.role == MessageRole.USER
            ),
            None,
        )
        if question is None:
            raise ValidationError("Нет вопроса, на который можно ответить заново")

        guard = check_user_input(question.content)
        if not guard.allowed:
            raise ValidationError(guard.message)

        level = resolve_level(parse_level(session.level))
        # Старый ответ в контекст не попадает: перегенерация его не видит.
        llm_messages = build_messages(
            level,
            self._history_for_llm(history[:index]),
            question.content,
        )
        previous_metadata = dict(target.message_metadata or {})
        answer = await self.provider.generate(llm_messages)
        new_message = await self._save_assistant_answer(session, answer, level)

        metadata = dict(previous_metadata)
        metadata["replaced"] = True
        metadata["replaced_by"] = str(new_message.id)
        target.message_metadata = metadata
        flag_modified(target, "message_metadata")
        await self.db.commit()
        await self.db.refresh(target)
        return new_message

    async def stream_reply(
        self,
        session: ChatSession,
        content: str,
        task_id: UUID | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        """Потоковый ответ: сообщение ученика сохраняется сразу,
        дельты отдаются по мере поступления.

        `stop_event` (S43-002) — сигнал остановки: генерация прерывается на
        ближайшей дельте. Ответ ассистента сохраняет вызывающий
        (`save_reply`), чтобы частичный ответ фиксировался и при обрыве
        соединения.

        `task_id` (S42-006) — контекст задачи для этого ответа; в историю
        он попадает только как метаданные вопроса.
        """
        text = content.strip()
        if not text:
            raise ValidationError("Сообщение не может быть пустым")

        task = await self._task_for_context(task_id)
        task_context = build_task_context_message(task) if task else None
        metadata = task_context_metadata(task) if task else None

        # S38-004: тот же фильтр для WS-стриминга.
        guard = check_user_input(text)
        if not guard.allowed:
            raise ValidationError(guard.message)

        self.last_warnings = []
        user_embedding = await try_embed(self.embedding_provider, text)
        await self.messages.create_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=text,
            metadata=metadata,
            embedding=user_embedding,
        )
        await self._remember_user_message(session, text)
        history = await self.get_history(session.id)
        level = resolve_level(parse_level(session.level))
        llm_messages = build_messages(
            level,
            self._history_for_llm(history),
            text,
            task_context=task_context,
        )

        async for delta in self.provider.stream(llm_messages):
            yield delta
            if stop_event is not None and stop_event.is_set():
                logger.info("chat_stream_stopped", session_id=str(session.id))
                break
