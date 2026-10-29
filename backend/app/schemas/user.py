"""
Pydantic schemas for User model
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserLevel, UserRole


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    # max_length=72 — ограничение bcrypt (пароль длиннее не хэшируется)
    password: str = Field(..., min_length=8, max_length=72)
    role: UserRole | None = UserRole.STUDENT
    level: UserLevel | None = UserLevel.BASIC


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=100)
    level: UserLevel | None = None
    settings: dict[str, Any] | None = None


class LevelUpdateRequest(BaseModel):
    """Смена уровня помощи (S5-002)"""

    level: UserLevel


class UserResponse(UserBase):
    """Схема ответа с пользователем"""

    id: UUID
    role: UserRole
    level: UserLevel
    created_at: datetime
    last_active: datetime
    settings: dict[str, Any]

    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    """Схема пользователя с паролем (для внутреннего использования)"""
    hashed_password: str
