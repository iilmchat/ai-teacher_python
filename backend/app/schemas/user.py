"""
Pydantic schemas for User model
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.user import UserLevel, UserRole

#: Максимум сниппетов кода в личных настройках (S44-003)
MAX_CODE_SNIPPETS = 20
#: Максимальная длина названия сниппета
MAX_SNIPPET_NAME_LENGTH = 80
#: Максимальная длина кода сниппета — как у запуска в песочнице
MAX_SNIPPET_CODE_LENGTH = 20_000


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


class CodeSnippet(BaseModel):
    """Сниппет кода в личных настройках (S44-003)"""

    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=MAX_SNIPPET_NAME_LENGTH)
    code: str = Field(..., min_length=1, max_length=MAX_SNIPPET_CODE_LENGTH)


class UserSettingsUpdate(BaseModel):
    """Обновление личных настроек пользователя (S43-004, S44-003).

    Список настроек закрытый: в `users.settings` попадают только известные
    ключи, чтобы клиент не мог записать в профиль произвольные данные.
    `prompt_template` — id выбранного шаблона промпта; `null` — сброс.
    `snippets` — полный список сниппетов кода; `null` — очистить.
    """

    prompt_template: str | None = Field(default=None, max_length=64)
    snippets: list[CodeSnippet] | None = Field(
        default=None, max_length=MAX_CODE_SNIPPETS
    )
    # S45-004: язык интерфейса и настройки уведомлений
    language: Literal["ru", "en"] | None = None
    email_notifications: bool | None = None
    deadline_notifications: bool | None = None
    deadline_days: int | None = Field(default=None, ge=1, le=14)

    @model_validator(mode="after")
    def _snippet_ids_are_unique(self) -> "UserSettingsUpdate":
        """Одинаковые id сниппетов сделали бы удаление неоднозначным."""
        if self.snippets is not None:
            ids = [snippet.id for snippet in self.snippets]
            if len(ids) != len(set(ids)):
                raise ValueError("Идентификаторы сниппетов должны быть уникальны")
        return self


class DeleteAccountRequest(BaseModel):
    """Подтверждение удаления аккаунта паролем (S26-004)"""

    password: str = Field(..., min_length=1, max_length=72)


def _validate_password_bytes(value: str) -> None:
    """Bcrypt не хэширует пароли длиннее 72 байт (S45-001)"""
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Пароль не должен превышать 72 байта")


class PasswordChangeRequest(BaseModel):
    """Смена пароля текущего пользователя (S45-001)"""

    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)

    @model_validator(mode="after")
    def _new_password_fits_bcrypt(self) -> "PasswordChangeRequest":
        _validate_password_bytes(self.new_password)
        return self


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
