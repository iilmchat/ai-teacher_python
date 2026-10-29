"""
WebSocket-эндпоинт чата со стримингом ответа LLM (S4-006, S11-004).

Протокол (JSON-сообщения):

Клиент → сервер:
    {"type": "chat", "content": "текст вопроса"}
    {"type": "ping"}

Сервер → клиент:
    {"type": "start"}
    {"type": "token", "content": "дельта"}
    {"type": "done", "content": "полный ответ"}
    {"type": "error", "detail": "текст ошибки"}
    {"type": "pong"}

Аутентификация: JWT access-токен в query-параметре `token`
(браузерный WebSocket не умеет передавать заголовок Authorization).

Протокол вынесен в `serve_chat_socket`, поэтому он покрывается тестами без
реального сокета (см. `tests/test_websocket_stream.py`).
"""

import json
from typing import Any, Protocol
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.chat import get_llm_provider
from app.core.security import decode_token
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.errors import AccessDeniedError, AppError, NotFoundError
from app.models.chat import ChatSession
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.llm import LLMProvider, LLMUnavailableError

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Chat WebSocket"])


class WebSocketLike(Protocol):
    """Минимальный интерфейс сокета для тестируемости протокола"""

    async def send_text(self, data: str) -> None: ...

    async def receive_text(self) -> str: ...


async def _send(ws: WebSocketLike, payload: dict[str, str]) -> None:
    """Отправить JSON-сообщение клиенту"""
    await ws.send_text(json.dumps(payload, ensure_ascii=False))


async def serve_chat_socket(
    ws: WebSocketLike,
    service: ChatService,
    session: ChatSession,
) -> None:
    """Цикл обработки сообщений чата.

    Бросает `WebSocketDisconnect`, когда клиент закрыл соединение.
    """
    while True:
        raw = await ws.receive_text()
        try:
            message: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await _send(ws, {"type": "error", "detail": "Ожидается JSON"})
            continue

        message_type = message.get("type")
        if message_type == "ping":
            await _send(ws, {"type": "pong"})
            continue

        if message_type != "chat":
            await _send(ws, {"type": "error", "detail": "Неизвестный тип сообщения"})
            continue

        content = str(message.get("content", ""))
        await _send(ws, {"type": "start"})

        chunks: list[str] = []
        try:
            async for delta in service.stream_reply(session, content):
                chunks.append(delta)
                await _send(ws, {"type": "token", "content": delta})
        except LLMUnavailableError as exc:
            logger.warning("llm_stream_failed", error=str(exc))
            await _send(ws, {"type": "error", "detail": str(exc)})
            continue
        except AppError as exc:
            await _send(ws, {"type": "error", "detail": exc.detail})
            continue

        await _send(ws, {"type": "done", "content": "".join(chunks)})


def _extract_user_id(token: str) -> UUID | None:
    """Проверить access-токен и вернуть id пользователя"""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    try:
        return UUID(subject)
    except ValueError:
        return None


@router.websocket("/api/v1/chat/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = "",
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
) -> None:
    """Стриминг ответов ассистента в реальном времени"""
    await websocket.accept()

    user_id = _extract_user_id(token)
    if user_id is None:
        await _send(websocket, {"type": "error", "detail": "Требуется авторизация"})
        await websocket.close(code=4401)
        return

    user: User | None = await UserRepository(db).get(user_id)
    if user is None:
        await _send(websocket, {"type": "error", "detail": "Пользователь не найден"})
        await websocket.close(code=4401)
        return

    service = ChatService(db, provider)
    try:
        session = await service.get_session(session_id, user)
    except (NotFoundError, AccessDeniedError) as exc:
        await _send(websocket, {"type": "error", "detail": exc.detail})
        await websocket.close(code=4404)
        return

    try:
        await serve_chat_socket(websocket, service, session)
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=str(session_id))
    finally:
        await provider.close()
