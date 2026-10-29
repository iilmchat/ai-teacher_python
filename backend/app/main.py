"""
AI Teacher for Python - Main FastAPI Application
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import websocket
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
from app.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.db.database import async_session_factory
from app.db.redis import close_redis, ping_redis
from app.errors import AppError
from app.services.llm import LLMError, LLMUnavailableError, create_llm_provider
from app.services.llm.health import check_provider_health
from app.services.seed_service import seed_tasks

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управление жизненным циклом приложения"""
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

    yield
    await close_redis()
    logger.info("app_stopped", app_name=settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-ассистент для обучения школьников программированию на Python",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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
