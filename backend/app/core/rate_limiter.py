"""
Rate limiting через Redis (S11-003).

`RateLimitMiddleware` работает по принципу fail-open: если Redis недоступен,
запрос пропускается с предупреждением в логе — защита не должна ронять API.

Лимиты:
- `POST /auth/login` — 5 запросов в минуту на IP;
- остальные запросы — 300 в минуту на IP;
- служебные пути (`/health`, `/docs`, `/openapi.json`, `/`) не лимитируются.

В тестах лимиты отключаются флагом `RATE_LIMIT_ENABLED=false`.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis
import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = structlog.get_logger(__name__)

#: Пути, которые не лимитируются
EXEMPT_PATHS: frozenset[str] = frozenset(
    {"/", "/api/v1/health", "/api/docs", "/api/redoc", "/api/openapi.json"}
)

LOGIN_PATH = "/api/v1/auth/login"
LOGIN_LIMIT = 5
GENERAL_LIMIT = 300
WINDOW_SECONDS = 60

PREFIX = "rate_limit"


class RateLimiter:
    """Счётчик запросов в Redis"""

    def __init__(self, redis_client: "redis.Redis[Any]") -> None:
        self.redis = redis_client

    async def is_limited(self, key: str, limit: int, period: int = WINDOW_SECONDS) -> bool:
        """Увеличить счётчик и сказать, превышен ли лимит"""
        full_key = f"{PREFIX}:{key}"
        current = await self.redis.get(full_key)

        if current is None:
            await self.redis.setex(full_key, period, 1)
            return False

        count = int(current)
        if count >= limit:
            return True

        await self.redis.incr(full_key)
        return False

    async def get_remaining(self, key: str, limit: int) -> int:
        """Сколько запросов осталось"""
        current = await self.redis.get(f"{PREFIX}:{key}")
        if current is None:
            return limit
        return max(0, limit - int(current))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware лимитов; Redis берётся через фабрику при первом запросе"""

    def __init__(
        self,
        app: Any,
        redis_factory: Callable[[], "redis.Redis[Any]"] | None = None,
    ) -> None:
        super().__init__(app)
        if redis_factory is None:
            from app.db.redis import get_redis

            redis_factory = get_redis
        self.redis_factory = redis_factory

    def _client_ip(self, request: Request) -> str:
        """IP клиента: за прокси учитываем X-Forwarded-For"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        try:
            limiter = RateLimiter(self.redis_factory())
        except Exception as exc:  # noqa: BLE001 — Redis недоступен
            logger.warning("rate_limit_unavailable", error=str(exc))
            return await call_next(request)

        is_login = request.url.path == LOGIN_PATH and request.method == "POST"
        key = (
            f"login:{self._client_ip(request)}"
            if is_login
            else f"general:{self._client_ip(request)}"
        )
        limit = LOGIN_LIMIT if is_login else GENERAL_LIMIT

        try:
            limited = await limiter.is_limited(key, limit=limit)
        except Exception as exc:  # noqa: BLE001 — fail-open при сбое Redis
            logger.warning("rate_limit_check_failed", error=str(exc))
            return await call_next(request)

        if limited:
            logger.info("rate_limit_exceeded", path=request.url.path, key=key)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Слишком много запросов. Попробуйте позже."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        return await call_next(request)
