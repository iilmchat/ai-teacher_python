"""
Схемы админ-панели (S10-004).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.task import TaskDifficulty
from app.models.user import UserLevel, UserRole
from app.schemas.audit import AuditLogItem


class AdminUserItem(BaseModel):
    """Пользователь в списке админки"""

    id: UUID
    email: EmailStr
    username: str
    role: UserRole
    level: UserLevel
    is_active: bool
    created_at: datetime
    last_active: datetime

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    """Изменение пользователя администратором"""

    role: UserRole | None = None
    level: UserLevel | None = None
    #: Мягкая деактивация (D-004): `false` отзывает сессии и токены
    is_active: bool | None = None


class AdminUserProgress(BaseModel):
    """Прогресс пользователя для карточки (S47-002)"""

    #: Задач решено (статус `completed`)
    solved: int
    #: Сумма попыток по всем задачам
    attempts: int


class AdminUserSessionItem(BaseModel):
    """Действующая сессия пользователя без служебного `jti` (S47-002)"""

    id: UUID
    created_at: datetime
    last_used_at: datetime
    user_agent: str | None = None
    ip: str | None = None


class AdminUserDetail(BaseModel):
    """Карточка пользователя: профиль, прогресс, аудит и сессии (S47-002)"""

    user: AdminUserItem
    progress: AdminUserProgress
    audit: list[AuditLogItem] = Field(default_factory=list)
    sessions: list[AdminUserSessionItem] = Field(default_factory=list)


class AdminUserBulkChanges(BaseModel):
    """Изменения для массовой операции (D-005)"""

    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_change(self) -> "AdminUserBulkChanges":
        if self.role is None and self.is_active is None:
            raise ValueError("Нужно указать role или is_active")
        return self


class AdminUserBulkRequest(BaseModel):
    """Массовое изменение пользователей (D-005), не больше 100 за запрос"""

    user_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    changes: AdminUserBulkChanges


class AdminUserSkipped(BaseModel):
    """Пропущенный пользователь и причина"""

    id: UUID
    reason: Literal["not_found", "self", "admin_role", "no_changes"]


class AdminUserBulkResponse(BaseModel):
    """Отчёт массовой операции: применённые и пропущенные (D-005)"""

    updated: list[UUID] = Field(default_factory=list)
    skipped: list[AdminUserSkipped] = Field(default_factory=list)


class AdminUserListResponse(BaseModel):
    """Список пользователей с пагинацией"""

    total: int
    items: list[AdminUserItem]


class AdminTaskItem(BaseModel):
    """Задача в админке (включая неактивные)"""

    id: UUID
    title: str
    difficulty: TaskDifficulty
    category: str
    is_active: bool
    test_cases_count: int
    hints_count: int
    created_at: datetime
    created_by: UUID | None


class AdminTaskListResponse(BaseModel):
    """Список задач для админки"""

    total: int
    items: list[AdminTaskItem]


class AnalyticsUsers(BaseModel):
    total: int
    by_role: dict[str, int]
    active_24h: int
    active_7d: int


class AnalyticsTasks(BaseModel):
    total: int
    active: int
    easy: int
    medium: int
    hard: int


class AnalyticsLearning(BaseModel):
    attempts: int
    completed: int
    started: int
    average_attempts: float


class AnalyticsActivity(BaseModel):
    sessions: int
    messages: int
    executions: int
    failed_executions: int


class AnalyticsLLMWindow(BaseModel):
    """Агрегаты LLM за окно времени (S12-003)"""

    window_hours: int
    requests: int
    errors: int
    avg_latency_ms: float
    p95_latency_ms: int
    avg_first_token_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    by_provider: dict[str, dict[str, float | int]]


class AnalyticsLLM(BaseModel):
    """Метрики LLM: час, сутки и число срабатываний fallback"""

    last_hour: AnalyticsLLMWindow
    last_24h: AnalyticsLLMWindow
    fallback_used: int
    recorded_at: str


class AnalyticsCache(BaseModel):
    """Метрики Redis-кэша справочников (S19-003)"""

    enabled: bool
    hits: int
    misses: int
    hit_rate: float
    sets: int
    invalidations: int
    errors: int


class AnalyticsResponse(BaseModel):
    """Сводка для дашборда"""

    users: AnalyticsUsers
    tasks: AnalyticsTasks
    learning: AnalyticsLearning
    activity: AnalyticsActivity
    llm: AnalyticsLLM
    cache: AnalyticsCache
    generated_at: str


class DeleteResponse(BaseModel):
    """Подтверждение удаления"""

    deleted: bool
    detail: str = Field(default="Пользователь удалён")


class QualityBreakdown(BaseModel):
    """Агрегат оценок по одному срезу (провайдер или модель)"""

    name: str
    total: int
    positive: int
    negative: int
    approval_rate: float


class QualityNegativeItem(BaseModel):
    """Негативная оценка с текстом ответа — вход для LLM-as-judge (S43-003)"""

    message_id: UUID
    comment: str | None = None
    content: str
    provider: str
    model: str
    created_at: datetime


class AdminQualityResponse(BaseModel):
    """Сводка качества ответов ассистента по оценкам учеников (S43-003)"""

    total: int
    positive: int
    negative: int
    approval_rate: float
    by_provider: list[QualityBreakdown] = Field(default_factory=list)
    by_model: list[QualityBreakdown] = Field(default_factory=list)
    negative_samples: list[QualityNegativeItem] = Field(default_factory=list)
    generated_at: str
