"""
Pydantic schemas for Chat model
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.chat import MessageRole


class ChatSessionBase(BaseModel):
    """Базовая схема сессии чата"""
    level: str = Field(default="basic", pattern="^(basic|intermediate|advanced)$")


class ChatSessionCreate(ChatSessionBase):
    """Схема для создания сессии чата"""
    pass


class ChatSessionResponse(ChatSessionBase):
    """Схема ответа с сессией чата"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ChatSessionWithMessages(ChatSessionResponse):
    """Схема сессии с сообщениями"""
    messages: List["ChatMessageResponse"] = []


class ChatMessageBase(BaseModel):
    """Базовая схема сообщения"""
    content: str
    code_blocks: List[str] = Field(default_factory=list)


class ChatMessageCreate(ChatMessageBase):
    """Схема для создания сообщения"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Схема ответа с сообщением"""
    id: UUID
    session_id: UUID
    role: MessageRole
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ChatMessageWithCode(ChatMessageResponse):
    """Схема сообщения с кодом"""
    code_blocks: List[dict] = Field(default_factory=list)


# Resolve forward references
ChatSessionWithMessages.model_rebuild()
