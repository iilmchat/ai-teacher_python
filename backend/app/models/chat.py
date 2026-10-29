"""
Chat models
"""
import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class MessageRole(str, enum.Enum):
    """Роль в чате"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(Base):
    """Модель сессии чата"""
    
    __tablename__ = "chat_sessions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="basic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<ChatSession {self.id} (user={self.user_id})>"


class ChatMessage(Base):
    """Модель сообщения чата"""
    
    __tablename__ = "chat_messages"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    code_blocks: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)  # OpenAI embedding size
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} ({self.role.value})>"
