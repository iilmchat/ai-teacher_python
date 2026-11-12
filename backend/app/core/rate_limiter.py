"""
Rate limiting через Redis (S11-003).

`RateLimitMiddleware` работает по принципу fail-open: если Redis недоступен,
запрос пропускается с предупреждением в логе — защита не должна ронять API.

Лимиты:
- `POST /auth/login` — 5 запросов в минуту на IP;
- `POST /auth/refresh` — 30 запросов в минуту на IP (S34-004);
- остальные запросы — 300 в минуту на IP;
- служебные пути (`/health`, `/docs`, `/openapi.json`, `/`) не лимитируются.

Per-user лимиты (не по IP): пробные проверки задачи (`CHECK_LIMIT`), запуск
кода в песочнице (`CODE_EXECUTE_LIMIT`) — см. `is_user_limited`.

В тестах лимиты отключаются флагом `RATE_LIMIT_ENABLED=false`.

S34-003: IP-адрес определяется через `client_ip(request)` с учётом доверенных прокси.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis
import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.ip_utils import client_ip
from app.core.metrics import rate_limit_blocked_observed

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

#: Лимит пробных проверок задачи на пользователя в минуту (S42-001).
#: Проверка запускает песочницу, поэтому она ограничена отдельно от
#: общего лимита по IP: один ученик не должен выжигать ресурсы сервера.
CHECK_LIMIT = 20

#: Отдельный лимит на обновление токенов (S34-004): защищает от перебора/флуда
#: refresh-эндпоинта, который выполняет bcrypt и работу с БД.
REFRESH_PATH = "/api/v1/auth/refresh"
REFRESH_LIMIT = 30

#: Лимит запусков кода на пользователя в минуту (S34-004). Песочница —
#: дорогой ресурс (процесс/контейнер), поэтому ограничена per-user, а не только
#: общим IP-лимитом.
CODE_EXECUTE_LIMIT = 30


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


async def is_user_limited(
    scope: str,
    user_id: str,
    limit: int,
    period: int = WINDOW_SECONDS,
) -> bool:
    """Лимит по конкретному пользователю (не по IP).

    Нужен там, где важна нагрузка одного пользователя, а не всего адреса:
    например, пробные проверки задачи запускают песочницу (S42-001).
    Fail-open: если Redis недоступен, запрос проходит — защита не должна
    ронять API.
    """
    if not settings.rate_limit_enabled:
        return False

    from app.db.redis import get_redis

    try:
        limiter = RateLimiter(get_redis())
        limited = await limiter.is_limited(f"{scope}:{user_id}", limit=limit, period=period)
        if limited:
            rate_limit_blocked_observed(scope)
        return limited
    except Exception as exc:  # noqa: BLE001 — fail-open при сбое Redis
        logger.warning("rate_limit_user_check_failed", scope=scope, error=str(exc))
        return False


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
        is_refresh = request.url.path == REFRESH_PATH and request.method == "POST"
        if is_login:
            key = f"login:{client_ip(request)}"
            limit = LOGIN_LIMIT
        elif is_refresh:
            key = f"refresh:{client_ip(request)}"
            limit = REFRESH_LIMIT
        else:
            key = f"general:{client_ip(request)}"
            limit = GENERAL_LIMIT

        try:
            limited = await limiter.is_limited(key, limit=limit)
        except Exception as exc:  # noqa: BLE001 — fail-open при сбое Redis
            logger.warning("rate_limit_check_failed", error=str(exc))
            return await call_next(request)

        if limited:
            logger.info("rate_limit_exceeded", path=request.url.path, key=key)
            rate_limit_blocked_observed(key.split(":", 1)[0])
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Слишком много запросов. Попробуйте позже."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        return await call_next(request)
