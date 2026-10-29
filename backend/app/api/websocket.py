"""
WebSocket-эндпоинт чата со стримингом ответа LLM (S4-006).

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
"""

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.db.database import async_session_factory
from app.db.repositories.user import UserRepository
from app.errors import AppError
from app.services.chat_service import ChatService
from app.services.llm import LLMUnavailableError, create_llm_provider

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Chat WebSocket"])


async def _send(ws: WebSocket, payload: dict[str, str]) -> None:
    """Отправить JSON-сообщение клиенту"""
    await ws.send_text(json.dumps(payload, ensure_ascii=False))


@router.websocket("/api/v1/chat/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: UUID, token: str = "") -> None:
    """Стриминг ответов ассистента в реальном времени"""
    await websocket.accept()

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await _send(websocket, {"type": "error", "detail": "Требуется авторизация"})
        await websocket.close(code=4401)
        return

    subject = payload.get("sub")
    if not isinstance(subject, str):
        await _send(websocket, {"type": "error", "detail": "Некорректный токен"})
        await websocket.close(code=4401)
        return

    provider = create_llm_provider()
    try:
        async with async_session_factory() as db:
            user = await UserRepository(db).get(UUID(subject))
            if user is None:
                await _send(websocket, {"type": "error", "detail": "Пользователь не найден"})
                await websocket.close(code=4401)
                return

            service = ChatService(db, provider)
            try:
                session = await service.get_session(session_id, user)
            except AppError as exc:
                await _send(websocket, {"type": "error", "detail": exc.detail})
                await websocket.close(code=4404)
                return

            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await _send(websocket, {"type": "error", "detail": "Ожидается JSON"})
                    continue

                message_type = message.get("type")
                if message_type == "ping":
                    await _send(websocket, {"type": "pong"})
                    continue

                if message_type != "chat":
                    await _send(
                        websocket, {"type": "error", "detail": "Неизвестный тип сообщения"}
                    )
                    continue

                content = str(message.get("content", ""))
                await _send(websocket, {"type": "start"})
                chunks: list[str] = []
                try:
                    async for delta in service.stream_reply(session, content):
                        chunks.append(delta)
                        await _send(websocket, {"type": "token", "content": delta})
                except LLMUnavailableError as exc:
                    logger.warning("llm_stream_failed", error=str(exc))
                    await _send(websocket, {"type": "error", "detail": str(exc)})
                    continue
                except AppError as exc:
                    await _send(websocket, {"type": "error", "detail": exc.detail})
                    continue

                await _send(websocket, {"type": "done", "content": "".join(chunks)})
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=str(session_id))
    finally:
        await provider.close()
