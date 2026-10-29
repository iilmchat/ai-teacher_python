"""
Chat API endpoints (S4-005).

Провайдер LLM приходит через зависимость `get_chat_service`, поэтому
в тестах он подменяется на фейковый без обращения к сети.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionWithMessages,
    ChatTurnResponse,
)
from app.services.chat_service import ChatService
from app.services.levels import list_levels
from app.services.llm import LLMProvider, create_llm_provider

router = APIRouter(prefix="/chat", tags=["Chat"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


def get_llm_provider() -> LLMProvider:
    """Провайдер LLM из настроек; переопределяется в тестах"""
    return create_llm_provider()


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_chat_service(db: DbSession, provider: LLMProviderDep) -> ChatService:
    """Сервис чата с провайдером LLM"""
    return ChatService(db, provider)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.get("/levels")
async def get_chat_levels() -> dict[str, list[dict[str, Any]]]:
    """Информация об уровнях ассистента (S5-004)"""
    return {
        "levels": [
            {
                "level": info.level.value,
                "title": info.title,
                "description": info.description,
                "audience": info.audience,
                "gives_ready_code": info.gives_ready_code,
            }
            for info in list_levels()
        ]
    }


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: ChatSessionCreate,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> ChatSessionResponse:
    """Создать сессию чата (уровень по умолчанию — уровень пользователя)"""
    session = await service.create_session(current_user, payload.level)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    current_user: CurrentUser,
    service: ChatServiceDep,
    skip: int = 0,
    limit: int = 100,
) -> list[ChatSessionResponse]:
    """Список сессий текущего пользователя"""
    sessions = await service.list_sessions(current_user, skip=skip, limit=limit)
    return [ChatSessionResponse.model_validate(item) for item in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> ChatSessionWithMessages:
    """Сессия с полной историей сообщений"""
    session = await service.get_session(session_id, current_user, with_messages=True)
    return ChatSessionWithMessages.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> None:
    """Удалить сессию вместе с сообщениями"""
    await service.delete_session(session_id, current_user)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: UUID,
    payload: ChatMessageRequest,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> ChatTurnResponse:
    """Отправить сообщение и получить ответ ассистента за один вызов"""
    session = await service.get_session(session_id, current_user)
    user_message, assistant_message = await service.send_message(
        session, payload.content
    )
    return ChatTurnResponse(
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant_message),
    )
