"""
Chat repository
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.base import BaseRepository
from app.models.chat import ChatSession, ChatMessage, MessageRole


class ChatSessionRepository(BaseRepository[ChatSession]):
    """Репозиторий для работы с сессиями чата"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ChatSession, session)
    
    async def get_with_messages(self, session_id: UUID) -> Optional[ChatSession]:
        """Получить сессию с сообщениями"""
        result = await self.session.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_sessions(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ChatSession]:
        """Получить сессии пользователя"""
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Репозиторий для работы с сообщениями чата"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ChatMessage, session)
    
    async def get_session_messages(
        self, session_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ChatMessage]:
        """Получить сообщения сессии"""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_message(
        self, session_id: UUID, role: MessageRole, content: str, code_blocks: List = None
    ) -> ChatMessage:
        """Создать сообщение"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            code_blocks=code_blocks or [],
        )
        return await self.create(message)
