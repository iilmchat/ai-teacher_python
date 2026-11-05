"""
Chat models
"""
import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

#: Размерность эмбеддингов сообщений (S19-005); совпадает с колонкой в БД
EMBEDDING_DIM = 1536


class MessageRole(str, enum.Enum):
    """Роль в чате"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(Base):
    """Модель сессии чата"""

    __tablename__ = "chat_sessions"
    # Индексы совпадают с миграциями 001 и 016 (иначе `alembic check` падает)
    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id"),
        # S43-001: список сессий — закреплённые сверху, затем по updated_at
        Index(
            "idx_chat_sessions_user_pinned_updated",
            "user_id",
            "pinned",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[str] = mapped_column(String(20), default="basic", nullable=False)
    #: Заголовок сессии (S43-001): auto из первого вопроса или задан вручную
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Закреплённая сессия всегда выше остальных в списке (S43-001)
    pinned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # Атрибут называется session_metadata: имя `metadata` занято DeclarativeBase
    session_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict
    )

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.id} (user={self.user_id})>"


class ChatMessage(Base):
    """Модель сообщения чата"""

    __tablename__ = "chat_messages"
    # Индексы совпадают с миграциями 001 и 0010 (иначе `alembic check` падает)
    __table_args__ = (
        Index("idx_chat_messages_session", "session_id"),
        # S19-004: история сессии читается с сортировкой по created_at
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
        # S19-005: HNSW-индекс для семантического поиска (косинусное расстояние)
        Index(
            "idx_chat_messages_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # values_callable: в БД хранятся значения ('assistant'), а не имена ('ASSISTANT')
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    code_blocks: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    # Метаданные ответа: провайдер, модель, версия промпта, предупреждения
    # (S12-006). Имя атрибута отличается от колонки: `metadata` занято
    # DeclarativeBase.
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    # 1536 — размерность эмбеддингов, используемая в проекте
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} ({self.role.value})>"
