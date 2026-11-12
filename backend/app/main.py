"""
AI Teacher for Python - Main FastAPI Application
"""
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypedDict

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import websocket
from app.api.health import router as health_router
from app.api.v1 import (
    admin,
    auth,
    chat,
    classrooms,
    code,
    engagement,
    tasks,
    teacher,
    users,
)
from app.config import settings, validate_security_settings
from app.core.logging import configure_logging
from app.core.metrics import (
    HTTPMetricsMiddleware,
    render_metrics,
    set_build_info,
    worker_info_observed,
)
from app.core.rate_limiter import RateLimitMiddleware
from app.core.request_context import RequestContextMiddleware
from app.core.runner_pool import close_current_pool as close_executor_pool
from app.core.sentry import init_sentry
from app.db.database import async_session_factory
from app.db.redis import close_redis, ping_redis
from app.errors import AppError
from app.services.llm import LLMError, LLMUnavailableError, create_llm_provider
from app.services.llm.health import check_provider_health
from app.services.scheduler import SchedulerHandle, start_scheduler, stop_scheduler
from app.services.seed_service import seed_tasks

configure_logging()
# S35-002: no-op без SENTRY_DSN; ошибки инициализации не роняют старт.
init_sentry()

logger = structlog.get_logger(__name__)


class DocsConfig(TypedDict):
    """URL-ы документации API (S34-006)."""

    docs_url: str | None
    redoc_url: str | None
    openapi_url: str | None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управление жизненным циклом приложения"""
    # S34-005: fail-fast при небезопасном SECRET_KEY в production.
    validate_security_settings()
    set_build_info(settings.version)
    # S35-001: каждая реплика отмечает свой pid — smoke-проверка агрегации.
    worker_info_observed(os.getpid())
    redis_ok = await ping_redis()
    logger.info(
        "app_starting",
        app_name=settings.app_name,
        version=settings.version,
        redis_available=redis_ok,
        rate_limit_enabled=settings.rate_limit_enabled,
    )

    if settings.seed_on_start:
        try:
            async with async_session_factory() as session:
                created = await seed_tasks(session)
            logger.info("seed_completed", created=created)
        except Exception as exc:  # noqa: BLE001 — seed не должен валить старт
            logger.warning("seed_failed", error=str(exc))

    scheduler: SchedulerHandle | None = None
    if settings.retention_scheduler_enabled:
        scheduler = start_scheduler(
            batch_size=settings.retention_scheduler_batch_size
        )

    yield
    # Планировщик retention (KI-025): сначала остановить его (ему нужна БД),
    # затем закрыть пул песочницы и Redis.
    await stop_scheduler(scheduler)
    # Пул песочницы (S23-002): тёплые интерпретаторы не должны переживать
    # приложение — иначе они останутся висеть до выхода процесса.
    await close_executor_pool()
    await close_redis()
    logger.info("app_stopped", app_name=settings.app_name)


def docs_urls(enabled: bool) -> DocsConfig:
    """URL-ы документации API с учётом флага `DOCS_ENABLED` (S34-006).

    При `enabled=False` Swagger, ReDoc и OpenAPI-схема не отдаются:
    FastAPI получает `None` и не регистрирует маршруты.
    """
    if not enabled:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {
        "docs_url": "/api/docs",
        "redoc_url": "/api/redoc",
        "openapi_url": "/api/openapi.json",
    }


_docs = docs_urls(settings.docs_enabled)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-ассистент для обучения школьников программированию на Python",
    lifespan=lifespan,
    docs_url=_docs["docs_url"],
    redoc_url=_docs["redoc_url"],
    openapi_url=_docs["openapi_url"],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (fail-open: если Redis недоступен, запросы проходят)
app.add_middleware(RateLimitMiddleware)

# Метрики и request-id (S25-001/002). Порядок важен: последний добавленный
# middleware — самый внешний, поэтому RequestContext оборачивает метрики и
# request_id привязан до записи метрик/логов.
app.add_middleware(HTTPMetricsMiddleware)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Доменные ошибки сервисов → корректные HTTP-ответы"""
    logger.info(
        "domain_error",
        path=request.url.path,
        status=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(
    request: Request, exc: LLMUnavailableError
) -> JSONResponse:
    """Провайдер LLM недоступен → 503 вместо 500 и «тихого» пустого ответа"""
    logger.error("llm_unavailable", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# Include routers
app.include_router(health_router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(code.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(teacher.router, prefix="/api/v1")
app.include_router(classrooms.router, prefix="/api/v1")
app.include_router(engagement.router, prefix="/api/v1")
app.include_router(websocket.router)


if settings.metrics_enabled:

    @app.get(settings.metrics_path, include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Prometheus-метрики (S25-002): без авторизации, только внутренняя сеть.

        В nginx `/metrics` наружу не публикуется (см. DESIGN_ADMIN_AND_OPS).
        """
        body, content_type = render_metrics()
        return Response(content=body, headers={"Content-Type": content_type})


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint.

    Секция `llm` показывает состояние провайдера: `ok`, `degraded` или
    `not_configured` (S12-001). Результат проверки кэшируется на 60 секунд,
    чтобы мониторинг не создавал нагрузку на API модели.
    """
    provider = None
    try:
        provider = create_llm_provider()
        llm_health: dict[str, Any] = (await check_provider_health(provider)).as_dict()
    except LLMError as exc:
        logger.warning("llm_health_failed", error=str(exc))
        llm_health = {
            "provider": settings.llm_provider,
            "model": None,
            "configured": False,
            "reachable": False,
            "status": "not_configured",
            "fallback": None,
        }
    finally:
        if provider is not None:
            await provider.close()

    return {
        "status": "ok",
        "version": settings.version,
        "app_name": settings.app_name,
        "llm_provider": settings.llm_provider,
        "llm": llm_health,
    }


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
