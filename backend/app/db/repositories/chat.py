"""
Chat repository
"""
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.base import BaseRepository
from app.models.chat import ChatMessage, ChatSession, MessageRole


class ChatSessionRepository(BaseRepository[ChatSession]):
    """Репозиторий для работы с сессиями чата"""

    def __init__(self, session: AsyncSession):
        super().__init__(ChatSession, session)

    async def get_with_messages(self, session_id: UUID) -> ChatSession | None:
        """Получить сессию с сообщениями"""
        result = await self.session.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ChatSession]:
        """Получить сессии пользователя"""
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Репозиторий для работы с сообщениями чата"""

    def __init__(self, session: AsyncSession):
        super().__init__(ChatMessage, session)

    async def get_session_messages(
        self, session_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ChatMessage]:
        """Получить сообщения сессии"""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search_user_messages_ilike(
        self, user_id: UUID, query: str, limit: int
    ) -> list[ChatMessage]:
        """Поиск по подстроке только в сессиях пользователя (S19-005).

        Фильтр по `ChatSession.user_id` — единственная граница изоляции:
        в выдачу не могут попасть сообщения чужих сессий.
        """
        pattern = f"%{query.strip().lower()}%"
        result = await self.session.execute(
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.user_id == user_id,
                func.lower(ChatMessage.content).like(pattern),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search_user_messages_semantic(
        self, user_id: UUID, embedding: list[float], limit: int
    ) -> list[tuple[ChatMessage, float]]:
        """Семантический поиск по эмбеддингам сообщений пользователя (S19-005).

        Сортировка — по косинусному расстоянию (индекс HNSW); в ответ попадает
        близость `1 - distance`, чтобы клиент видел score, а не расстояние.
        Сообщения без эмбеддинга исключены.
        """
        vector_column = cast(Any, ChatMessage.embedding)
        distance = vector_column.cosine_distance(embedding)
        result = await self.session.execute(
            select(ChatMessage, distance.label("distance"))
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.user_id == user_id,
                ChatMessage.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
        return [
            (row[0], round(1.0 - float(row[1]), 4)) for row in result.all()
        ]

    async def create_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
        code_blocks: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> ChatMessage:
        """Создать сообщение (embedding — best-effort вектор, S19-005)"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            code_blocks=code_blocks or [],
            message_metadata=metadata or {},
            embedding=embedding,
        )
        return await self.create(message)
