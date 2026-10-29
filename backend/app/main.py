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
from app.api.v1 import admin, auth, chat, code, tasks, users
from app.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.db.redis import close_redis, ping_redis
from app.errors import AppError

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


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(code.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(websocket.router)


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": settings.version,
        "app_name": settings.app_name,
        "llm_provider": settings.llm_provider,
    }


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
