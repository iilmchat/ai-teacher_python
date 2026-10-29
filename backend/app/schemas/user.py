"""
Pydantic schemas for User model
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole, UserLevel


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    password: str = Field(..., min_length=8, max_length=100)
    role: Optional[UserRole] = UserRole.STUDENT
    level: Optional[UserLevel] = UserLevel.BASIC


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    level: Optional[UserLevel] = None
    settings: Optional[dict] = None


class UserResponse(UserBase):
    """Схема ответа с пользователем"""
    id: UUID
    role: UserRole
    level: UserLevel
    created_at: datetime
    last_active: datetime
    settings: dict
    
    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    """Схема пользователя с паролем (для внутреннего использования)"""
    hashed_password: str
