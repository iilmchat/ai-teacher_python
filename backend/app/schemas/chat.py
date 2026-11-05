"""
Pydantic schemas for Chat model
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.chat import ChatMessage, MessageRole
from app.models.user import UserLevel


class ChatSessionBase(BaseModel):
    """Базовая схема сессии чата"""

    level: str = Field(default="basic", pattern="^(basic|intermediate|advanced)$")


class ChatSessionCreate(BaseModel):
    """Схема для создания сессии чата.

    `level` необязателен: если не передан, сессия наследует уровень профиля
    пользователя (S5-002). Поэтому здесь нет дефолта "basic".
    """

    level: UserLevel | None = None


class ChatSessionResponse(ChatSessionBase):
    """Схема ответа с сессией чата"""

    id: UUID
    user_id: UUID
    #: Заголовок (S43-001): auto из первого вопроса или задан вручную
    title: str | None = None
    #: Закреплённая сессия в списке выше остальных (S43-001)
    pinned: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionUpdate(BaseModel):
    """Переименование и закрепление сессии (S43-001).

    Оба поля необязательны, но хотя бы одно должно быть передано. Пустой
    заголовок после trim отклоняется: заголовок либо есть, либо его нет
    (``None`` означает «не менять», а не «очистить»).
    """

    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Заголовок не может быть пустым")
        return normalized

    @model_validator(mode="after")
    def _require_change(self) -> "ChatSessionUpdate":
        if self.title is None and self.pinned is None:
            raise ValueError("Нужно передать title или pinned")
        return self


class ChatMessageBase(BaseModel):
    """Базовая схема сообщения"""

    content: str
    # Блоки кода приходят из БД как JSONB, поэтому тип гибкий
    code_blocks: list[Any] = Field(default_factory=list)


class ChatMessageCreate(ChatMessageBase):
    """Схема для создания сообщения"""


class ChatMessageResponse(ChatMessageBase):
    """Схема ответа с сообщением.

    `metadata` содержит провайдера, модель и версию промпта ответа
    (S12-006); `warnings` — коды нарушений политики уровня (S12-005).
    """

    id: UUID
    session_id: UUID
    role: MessageRole
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_message(cls, message: ChatMessage) -> "ChatMessageResponse":
        """Собрать ответ API из ORM-модели (колонка `metadata` — JSONB)"""
        metadata = dict(message.message_metadata or {})
        raw_warnings = metadata.get("warnings", [])
        warnings = (
            [str(code) for code in raw_warnings]
            if isinstance(raw_warnings, list)
            else []
        )
        return cls(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            code_blocks=list(message.code_blocks or []),
            created_at=message.created_at,
            metadata=metadata,
            warnings=warnings,
        )


class ChatSessionWithMessages(ChatSessionResponse):
    """Схема сессии с сообщениями"""

    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    """Запрос на отправку сообщения в чат.

    `task_id` (S42-006) — задача, условие которой ассистент получает
    отдельным системным сообщением. В `content` по-прежнему только текст
    вопроса: идентификатор не подмешивается в историю ученика.
    """

    content: str = Field(..., min_length=1, max_length=4000)
    task_id: UUID | None = None


class ChatTurnResponse(BaseModel):
    """Пара «вопрос ученика + ответ ассистента»"""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class ChatSearchItem(BaseModel):
    """Найденное сообщение в истории чата (S19-005)"""

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
    #: Косинусная близость для semantic-режима; ``None`` для ILIKE
    score: float | None = None


class ChatSearchResponse(BaseModel):
    """Результат поиска по истории чата: режим и найденные сообщения"""

    query: str
    mode: Literal["semantic", "ilike"]
    items: list[ChatSearchItem] = Field(default_factory=list)
    total: int

