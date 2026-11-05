"""
WebSocket-эндпоинт чата со стримингом ответа LLM (S4-006, S11-004, S43-002).

Протокол (JSON-сообщения):

Клиент → сервер:
    {"type": "chat", "content": "текст вопроса", "task_id": "<uuid>"}
    {"type": "stop"}
    {"type": "ping"}

`task_id` необязателен (S42-006): условие задачи уходит в LLM отдельным
системным сообщением, а в историю — только как метаданные вопроса.

`stop` (S43-002) — остановка генерации: сервер прерывает поток и
фиксирует частичный ответ.

Сервер → клиент:
    {"type": "start"}
    {"type": "token", "content": "дельта"}
    {"type": "done", "content": "полный ответ"}
    {"type": "stopped", "content": "частичный ответ"}
    {"type": "error", "detail": "текст ошибки"}
    {"type": "pong"}

Аутентификация: JWT access-токен в query-параметре `token`
(браузерный WebSocket не умеет передавать заголовок Authorization).

Протокол вынесен в `serve_chat_socket`, поэтому он покрывается тестами без
реального сокета (см. `tests/test_websocket_stream.py`).
"""

import asyncio
import json
from typing import Any, Protocol
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.chat import get_embedding_provider, get_llm_provider
from app.core.security import decode_token
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.errors import AccessDeniedError, AppError, NotFoundError, ValidationError
from app.models.chat import ChatSession
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.llm import LLMProvider, LLMUnavailableError
from app.services.llm.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Chat WebSocket"])

#: Сколько ждём завершения стрима при закрытии соединения (S43-002)
STREAM_DRAIN_TIMEOUT = 10.0


class WebSocketLike(Protocol):
    """Минимальный интерфейс сокета для тестируемости протокола"""

    async def send_text(self, data: str) -> None: ...

    async def receive_text(self) -> str: ...


async def _send(ws: WebSocketLike, payload: dict[str, Any]) -> None:
    """Отправить JSON-сообщение клиенту"""
    await ws.send_text(json.dumps(payload, ensure_ascii=False))


async def _send_safe(ws: WebSocketLike, payload: dict[str, Any]) -> None:
    """Отправить сообщение, не падая на закрытом соединении (S43-002)"""
    try:
        await _send(ws, payload)
    except (WebSocketDisconnect, RuntimeError, ConnectionError):
        logger.info("ws_send_failed_closed")


async def _stream_message(
    ws: WebSocketLike,
    service: ChatService,
    session: ChatSession,
    content: str,
    task_id: UUID | None,
    stop_event: asyncio.Event,
) -> None:
    """Отдать ответ ассистента дельтами и сохранить его (S43-002).

    Остановка (`stop_event`) прерывает поток на ближайшей дельте; частичный
    ответ сохраняется с пометкой `stopped` в метаданных.
    """
    chunks: list[str] = []
    stream = service.stream_reply(session, content, task_id, stop_event=stop_event)
    try:
        try:
            async for delta in stream:
                chunks.append(delta)
                await _send(ws, {"type": "token", "content": delta})
        except LLMUnavailableError as exc:
            logger.warning("llm_stream_failed", error=str(exc))
            await _send_safe(ws, {"type": "error", "detail": str(exc)})
            return
        except AppError as exc:
            await _send_safe(ws, {"type": "error", "detail": exc.detail})
            return
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            # Клиент отключился — частичный ответ всё равно фиксируем.
            stop_event.set()
            logger.info("ws_client_disconnected_mid_stream", session_id=str(session.id))
    finally:
        # Закрываем генератор: соединение с провайдером не должна висеть.
        await stream.aclose()

    answer = "".join(chunks).strip()
    stopped = stop_event.is_set()
    if answer:
        await service.save_reply(session, answer, stopped=stopped)
    if stopped:
        await _send_safe(
            ws,
            {
                "type": "stopped",
                "content": answer,
                "warnings": list(service.last_warnings),
            },
        )
    else:
        await _send_safe(
            ws,
            {
                "type": "done",
                "content": answer,
                # Нарушения политики уровня (S12-005) — клиент показывает плашку
                "warnings": list(service.last_warnings),
            },
        )


async def serve_chat_socket(
    ws: WebSocketLike,
    service: ChatService,
    session: ChatSession,
) -> None:
    """Цикл обработки сообщений чата.

    Генерация идёт в отдельной задаче: только так можно принять команду
    `stop` во время стриминга (S43-002).

    Бросает `WebSocketDisconnect`, когда клиент закрыл соединение.
    """
    stop_event = asyncio.Event()
    stream_task: asyncio.Task[None] | None = None

    try:
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

            if message_type == "stop":
                # Остановка текущей генерации (S43-002)
                stop_event.set()
                continue

            if message_type != "chat":
                await _send(ws, {"type": "error", "detail": "Неизвестный тип сообщения"})
                continue

            if stream_task is not None and not stream_task.done():
                await _send(
                    ws, {"type": "error", "detail": "Генерация уже выполняется"}
                )
                continue

            content = str(message.get("content", ""))
            try:
                task_id = _parse_task_id(message.get("task_id"))
            except ValidationError as exc:
                await _send(ws, {"type": "error", "detail": exc.detail})
                continue

            await _send(ws, {"type": "start"})
            stop_event = asyncio.Event()
            stream_task = asyncio.create_task(
                _stream_message(ws, service, session, content, task_id, stop_event)
            )
    finally:
        # Соединение закрыто: дожидаемся стрима, чтобы ответ сохранился.
        if stream_task is not None and not stream_task.done():
            try:
                await asyncio.wait_for(stream_task, timeout=STREAM_DRAIN_TIMEOUT)
            except TimeoutError:
                stream_task.cancel()
            except Exception:  # noqa: BLE001 — сокет уже закрыт, детали не важны
                logger.info("ws_stream_drain_failed")


def _parse_task_id(raw: object) -> UUID | None:
    """Разобрать необязательный `task_id` из сообщения сокета (S42-006)."""
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise ValidationError("Некорректный идентификатор задачи")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise ValidationError("Некорректный идентификатор задачи") from exc


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
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider),
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

    service = ChatService(db, provider, embedding_provider)
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
