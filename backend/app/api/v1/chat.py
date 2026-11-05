"""
Chat API endpoints (S4-005).

Провайдер LLM приходит через зависимость `get_chat_service`, поэтому
в тестах он подменяется на фейковый без обращения к сети.
"""

import json
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSearchItem,
    ChatSearchResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatSessionWithMessages,
    ChatTurnResponse,
    MessageFeedbackCreate,
    MessageFeedbackResponse,
)
from app.services.cache import cache_get_json, cache_set_json, levels_cache_key
from app.services.chat_export import (
    content_disposition,
    render_transcript_markdown,
    transcript_filename,
)
from app.services.chat_service import ChatService
from app.services.feedback_service import FeedbackService
from app.services.levels import list_levels
from app.services.llm import LLMProvider, create_llm_provider
from app.services.llm.embeddings import (
    EmbeddingProvider,
    create_embedding_provider,
)

router = APIRouter(prefix="/chat", tags=["Chat"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


def get_llm_provider() -> LLMProvider:
    """Провайдер LLM из настроек; переопределяется в тестах"""
    return create_llm_provider()


def get_embedding_provider() -> EmbeddingProvider | None:
    """Провайдер эмбеддингов для RAG-lite (S19-005); переопределяется в тестах"""
    return create_embedding_provider()


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
EmbeddingProviderDep = Annotated[
    EmbeddingProvider | None, Depends(get_embedding_provider)
]


def get_chat_service(
    db: DbSession,
    provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
) -> ChatService:
    """Сервис чата с провайдерами LLM и эмбеддингов"""
    return ChatService(db, provider, embedding_provider)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_feedback_service(db: DbSession) -> FeedbackService:
    """Сервис оценок ответов ассистента (S43-003)"""
    return FeedbackService(db)


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.get("/levels")
async def get_chat_levels() -> dict[str, list[dict[str, Any]]]:
    """Информация об уровнях ассистента (S5-004, кэш S19-003)"""
    key = levels_cache_key()
    cached = await cache_get_json(key)
    if isinstance(cached, dict):
        return cached

    payload = {
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
    await cache_set_json(key, payload)
    return payload


@router.post(
    "/sessions/{session_id}/messages/{message_id}/regenerate",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def regenerate_message(
    session_id: UUID,
    message_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> ChatMessageResponse:
    """Перегенерировать ответ ассистента (S43-002).

    Вопрос ученика не дублируется: ассистент отвечает заново на тот же
    вопрос с тем же уровнем. Прежний ответ остаётся в истории, но
    помечается в метаданных как заменённый.
    """
    session = await service.get_session(session_id, current_user)
    message = await service.regenerate_reply(session, message_id)
    return ChatMessageResponse.from_message(message)


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDep,
    format_: Literal["md", "json"] = Query(default="md", alias="format"),
) -> Response:
    """Выгрузка диалога (S43-004).

    `format=md` — Markdown-транскрипт для чтения, `format=json` — данные в том
    же виде, что и `GET /chat/sessions/{id}`. Чужая сессия — 403.
    """
    session = await service.get_session(session_id, current_user, with_messages=True)
    messages = list(session.messages)
    if format_ == "json":
        payload = ChatSessionWithMessages(
            id=session.id,
            user_id=session.user_id,
            level=session.level,
            title=session.title,
            pinned=session.pinned,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=[
                ChatMessageResponse.from_message(message) for message in messages
            ],
        )
        return Response(
            json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": content_disposition(
                    transcript_filename(session, "json")
                )
            },
        )
    markdown = render_transcript_markdown(session, messages)
    return Response(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": content_disposition(
                transcript_filename(session, "md")
            )
        },
    )


@router.post(
    "/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_message_feedback(
    message_id: UUID,
    payload: MessageFeedbackCreate,
    current_user: CurrentUser,
    service: FeedbackServiceDep,
) -> MessageFeedbackResponse:
    """Оценить ответ ассистента (S43-003).

    Повторная оценка меняет значение: на пару «сообщение × ученик» оценка
    всегда одна.
    """
    feedback = await service.set_feedback(
        message_id, current_user, payload.value, payload.comment
    )
    return MessageFeedbackResponse.model_validate(feedback)


@router.delete("/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_feedback(
    message_id: UUID,
    current_user: CurrentUser,
    service: FeedbackServiceDep,
) -> None:
    """Снять свою оценку ответа ассистента (S43-003)"""
    await service.remove_feedback(message_id, current_user)


@router.get(
    "/sessions/{session_id}/feedback",
    response_model=list[MessageFeedbackResponse],
)
async def list_session_feedback(
    session_id: UUID,
    current_user: CurrentUser,
    service: FeedbackServiceDep,
) -> list[MessageFeedbackResponse]:
    """Мои оценки по сообщениям сессии (S43-003)"""
    items = await service.list_for_session(session_id, current_user)
    return [MessageFeedbackResponse.model_validate(item) for item in items]


@router.get("/search", response_model=ChatSearchResponse)
async def search_chat_history(
    current_user: CurrentUser,
    service: ChatServiceDep,
    q: str = Query(..., min_length=1, max_length=200, description="Поисковый запрос"),
    limit: int | None = Query(default=None, ge=1, le=50),
) -> ChatSearchResponse:
    """Поиск по истории чата текущего пользователя (S19-005).

    С `RAG_ENABLED=true` и настроенным провайдером — семантический поиск
    (pgvector), иначе ILIKE по подстроке. Чужие сессии не попадают в выдачу
    никогда: фильтр по `chat_sessions.user_id` зашит в репозиторий.
    """
    effective_limit = limit or settings.rag_top_k
    mode, hits = await service.search(current_user, q, effective_limit)
    items = [
        ChatSearchItem(
            id=hit.message.id,
            session_id=hit.message.session_id,
            role=hit.message.role,
            content=hit.message.content,
            created_at=hit.message.created_at,
            score=hit.score,
        )
        for hit in hits
    ]
    return ChatSearchResponse(
        query=q, mode=mode, items=items, total=len(items)
    )


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
    """Сессия с полной историей сообщений (включая метаданные ответов)"""
    session = await service.get_session(session_id, current_user, with_messages=True)
    return ChatSessionWithMessages(
        id=session.id,
        user_id=session.user_id,
        level=session.level,
        title=session.title,
        pinned=session.pinned,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse.from_message(message) for message in session.messages
        ],
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: UUID,
    payload: ChatSessionUpdate,
    current_user: CurrentUser,
    service: ChatServiceDep,
) -> ChatSessionResponse:
    """Переименовать и/или закрепить сессию (S43-001)"""
    session = await service.update_session(
        session_id,
        current_user,
        title=payload.title,
        pinned=payload.pinned,
    )
    return ChatSessionResponse.model_validate(session)


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
        session, payload.content, payload.task_id
    )
    return ChatTurnResponse(
        user_message=ChatMessageResponse.from_message(user_message),
        assistant_message=ChatMessageResponse.from_message(assistant_message),
    )
