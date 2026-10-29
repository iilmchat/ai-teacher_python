"""
User model
"""
import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, Enum, Text
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
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    level: Mapped[UserLevel] = mapped_column(Enum(UserLevel), default=UserLevel.BASIC, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
