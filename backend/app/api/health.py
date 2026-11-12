"""Liveness/Readiness (S25-003).

- `/health/live` — процесс жив (ничего не проверяет, отвечает всегда);
- `/health/ready` — готов принимать трафик: БД, Redis, конфиг LLM. Любая
  зависимость недоступна → 503 с перечнем проверок;
- `/api/v1/health` остаётся обратно совместимым (детальный статус LLM).

Docker healthcheck и compose используют readiness (см. docker-compose*.yml).
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import set_dependency_up
from app.db.database import get_db
from app.db.redis import ping_redis

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Health"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Процесс жив: без обращений к зависимостям"""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: DbSession) -> Any:
    """Готовность: БД, Redis, конфиг LLM"""
    checks: dict[str, bool] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001 — readiness не должен падать 500
        logger.warning("readiness_database_failed", error=str(exc))
        checks["database"] = False

    try:
        checks["redis"] = await ping_redis()
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_redis_failed", error=str(exc))
        checks["redis"] = False

    # LLM — только конфиг (сетевой ping делает /api/v1/health, он кэшируется)
    checks["llm_configured"] = bool(
        settings.llm_provider and (settings.deepseek_api_key or settings.llm_provider == "echo")
    )

    ready = checks["database"] and checks["redis"]
    # S35-003: gauges для алертов DatabaseDown/RedisDown.
    set_dependency_up(database=checks["database"], redis=checks["redis"])
    payload = {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "version": settings.version,
    }
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload
