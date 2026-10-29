"""
Code API: выполнение, линтинг и анализ кода (S6-005).

Выполнение идёт через `SandboxedExecutor` (отдельный процесс + RestrictedPython).
Песочница приходит зависимостью, поэтому в тестах можно задать короткий таймаут.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.executor import SandboxedExecutor
from app.core.linter import analyze_code, lint_code
from app.core.security import get_current_active_user
from app.db.database import get_db
from app.db.repositories.code import CodeExecutionRepository
from app.models.code import CodeExecution
from app.models.user import User
from app.schemas.code import (
    AnalyzeResponse,
    CodeRequest,
    ExecutionRecordResponse,
    ExecutionResponse,
    LintIssueSchema,
    LintResponse,
)

router = APIRouter(prefix="/code", tags=["Code"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


def get_executor() -> SandboxedExecutor:
    """Песочница с таймаутом из настроек; переопределяется в тестах"""
    return SandboxedExecutor(timeout=float(settings.executor_timeout))


ExecutorDep = Annotated[SandboxedExecutor, Depends(get_executor)]


@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(
    payload: CodeRequest,
    current_user: CurrentUser,
    db: DbSession,
    executor: ExecutorDep,
) -> ExecutionResponse:
    """Выполнить код ученика в песочнице и сохранить результат"""
    result = await executor.execute(payload.code, payload.stdin or "")

    await CodeExecutionRepository(db).create(
        CodeExecution(
            user_id=current_user.id,
            code=payload.code,
            output=result.output,
            error=result.error,
            success=result.success,
            execution_time=result.execution_time,
        )
    )

    return ExecutionResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        error_type=result.error_type,
        execution_time=round(result.execution_time, 4),
        violations=result.violations,
    )


@router.post("/lint", response_model=LintResponse)
async def lint(payload: CodeRequest) -> LintResponse:
    """Проверить код без выполнения"""
    issues = lint_code(payload.code)
    return LintResponse(
        issues=[LintIssueSchema(**asdict(issue)) for issue in issues],
        errors=sum(1 for issue in issues if issue.severity == "error"),
        warnings=sum(1 for issue in issues if issue.severity == "warning"),
        infos=sum(1 for issue in issues if issue.severity == "info"),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: CodeRequest, current_user: CurrentUser) -> AnalyzeResponse:
    """Линт + метрики кода с коротким резюме для ученика"""
    issues, stats = analyze_code(payload.code)

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")

    if errors:
        summary = f"Найдено {errors} критичных проблем — код не запустится."
    elif warnings:
        summary = f"Код рабочий, но есть {warnings} замечаний по стилю."
    else:
        summary = "Код выглядит корректно. Можно запускать!"

    return AnalyzeResponse(
        issues=[LintIssueSchema(**asdict(issue)) for issue in issues],
        stats=stats.as_dict(),
        summary=summary,
    )


@router.get("/history", response_model=list[ExecutionRecordResponse])
async def get_history(
    current_user: CurrentUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 20,
) -> list[ExecutionRecordResponse]:
    """История запусков кода текущего пользователя"""
    executions = await CodeExecutionRepository(db).get_user_executions(
        current_user.id, skip=skip, limit=limit
    )
    return [ExecutionRecordResponse.model_validate(item) for item in executions]


@router.get("/history/{execution_id}", response_model=ExecutionRecordResponse)
async def get_execution(
    execution_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ExecutionRecordResponse:
    """Одна запись истории (только своя)"""
    from app.errors import AccessDeniedError, NotFoundError

    record = await CodeExecutionRepository(db).get(execution_id)
    if record is None:
        raise NotFoundError("Запись не найдена")
    if record.user_id != current_user.id:
        raise AccessDeniedError("Запись принадлежит другому пользователю")
    return ExecutionRecordResponse.model_validate(record)


@router.get("/limits", status_code=status.HTTP_200_OK)
async def get_limits() -> dict[str, object]:
    """Ограничения песочницы для отображения в интерфейсе"""
    from app.core.executor import ALLOWED_MODULES

    return {
        "timeout_seconds": settings.executor_timeout,
        "memory_limit_mb": settings.executor_memory_limit,
        "max_code_length": 20_000,
        "allowed_modules": sorted(ALLOWED_MODULES),
    }
