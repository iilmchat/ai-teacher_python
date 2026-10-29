"""
Pydantic schemas for Chat model
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.chat import MessageRole


class ChatSessionBase(BaseModel):
    """Базовая схема сессии чата"""

    level: str = Field(default="basic", pattern="^(basic|intermediate|advanced)$")


class ChatSessionCreate(ChatSessionBase):
    """Схема для создания сессии чата"""


class ChatSessionResponse(ChatSessionBase):
    """Схема ответа с сессией чата"""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageBase(BaseModel):
    """Базовая схема сообщения"""

    content: str
    # Блоки кода приходят из БД как JSONB, поэтому тип гибкий
    code_blocks: list[Any] = Field(default_factory=list)


class ChatMessageCreate(ChatMessageBase):
    """Схема для создания сообщения"""


class ChatMessageResponse(ChatMessageBase):
    """Схема ответа с сообщением"""

    id: UUID
    session_id: UUID
    role: MessageRole
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionWithMessages(ChatSessionResponse):
    """Схема сессии с сообщениями"""

    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    """Запрос на отправку сообщения в чат"""

    content: str = Field(..., min_length=1, max_length=4000)


class ChatTurnResponse(BaseModel):
    """Пара «вопрос ученика + ответ ассистента»"""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse

