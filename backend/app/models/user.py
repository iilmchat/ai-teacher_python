"""
User model
"""
import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserRole(str, enum.Enum):
    """Роли пользователей"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class UserLevel(str, enum.Enum):
    """Уровень ассистента"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class User(Base):
    """Модель пользователя"""

    __tablename__ = "users"
    # Индексы и уникальные ограничения описаны так же, как в миграции 001:
    # это нужно, чтобы `alembic check` не находил расхождений
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        UniqueConstraint("username", name="users_username_key"),
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # values_callable: в БД хранятся значения ('student'), а не имена членов ('STUDENT')
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=UserRole.STUDENT,
        nullable=False,
    )
    level: Mapped[UserLevel] = mapped_column(
        Enum(UserLevel, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=UserLevel.BASIC,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
