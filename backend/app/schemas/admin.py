"""
Схемы админ-панели (S10-004).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.task import TaskDifficulty
from app.models.user import UserLevel, UserRole


class AdminUserItem(BaseModel):
    """Пользователь в списке админки"""

    id: UUID
    email: EmailStr
    username: str
    role: UserRole
    level: UserLevel
    created_at: datetime
    last_active: datetime

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    """Изменение пользователя администратором"""

    role: UserRole | None = None
    level: UserLevel | None = None


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
