"""Request-ID и контекст запроса (S25-001).

Middleware:

* берёт `X-Request-ID` из входящего запроса или генерирует `uuid4`;
* кладёт `request_id` в `structlog.contextvars` — он попадает во все записи
  логов, включая вызовы LLM/песочницы внутри запроса;
* возвращает `X-Request-ID` в ответе (удобно сопоставлять с логами и клиентом);
* пишет одну структурированную запись `http_request` с методом, путём,
  статусом и длительностью.

`request_id()` доступен сервисам без передачи аргументов — через contextvars.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def current_request_id() -> str | None:
    """Request-ID текущего запроса (или None вне запроса)"""
    value = structlog.contextvars.get_contextvars().get("request_id")
    return str(value) if value else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request-ID, контекст structlog и лог запроса"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = (incoming or "").strip()[:128] or uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 1),
            )
            raise
        finally:
            pass

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return response
