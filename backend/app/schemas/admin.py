"""
Схемы админ-панели (S10-004).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.task import TaskDifficulty
from app.models.user import UserLevel, UserRole

#: Источники, которые попадают в очередь модерации (S47-003)
ModerationSource = Literal["generated", "imported"]

#: Действия модератора (S47-003)
ModerationAction = Literal["publish", "unpublish", "return_to_revision"]


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


class QualityTopic(BaseModel):
    """Негативная оценка в разрезе категории/тега задачи (S47-004).

    `kind="none"` — ответ пришёл без контекста задачи (D-003); `name` в этом
    случае — «без задачи».
    """

    kind: Literal["category", "tag", "none"]
    name: str
    negative: int


class AdminQualityResponse(BaseModel):
    """Сводка качества ответов ассистента по оценкам учеников (S43-003/S47-004)"""

    total: int
    positive: int
    negative: int
    approval_rate: float
    by_provider: list[QualityBreakdown] = Field(default_factory=list)
    by_model: list[QualityBreakdown] = Field(default_factory=list)
    #: Срез по уровню помощи из ChatSession.level (S47-004)
    by_level: list[QualityBreakdown] = Field(default_factory=list)
    #: Топ категорий/тегов задач по негативным оценкам (S47-004)
    top_problem_topics: list[QualityTopic] = Field(default_factory=list)
    negative_samples: list[QualityNegativeItem] = Field(default_factory=list)
    generated_at: str


class ModerationMetrics(BaseModel):
    """Метрики «застревания» задачи в очереди модерации (S47-003)"""

    #: Засчитанные попытки из task_attempts
    attempts: int = 0
    #: Сколько из них прошло все тест-кейсы
    passed_attempts: int = 0
    #: Доля успешных попыток: passed_attempts / attempts (0, если попыток нет)
    success_rate: float = 0.0
    #: Среднее число попыток на ученика, у которого есть прогресс
    avg_attempts: float = 0.0
    #: Ученики с attempts > 0
    students: int = 0
    #: Ученики с attempts > threshold и незавершённой задачей
    stuck_students: int = 0


class ModerationAttemptItem(BaseModel):
    """Последняя попытка по задаче в карточке модератора (S47-003)"""

    id: UUID
    user_id: UUID
    username: str
    passed: bool
    passed_count: int
    total_count: int
    created_at: datetime


class AdminTaskReviewItem(BaseModel):
    """Задача в очереди модерации с метриками (S47-003)"""

    id: UUID
    title: str
    description: str
    difficulty: TaskDifficulty
    category: str
    source: str
    is_active: bool
    moderation_comment: str | None = None
    test_cases_count: int
    hints_count: int
    created_at: datetime
    metrics: ModerationMetrics
    #: Последние попытки (новые сверху) — для карточки в интерфейсе
    recent_attempts: list[ModerationAttemptItem] = Field(default_factory=list)


class AdminTaskReviewResponse(BaseModel):
    """Очередь модерации: только generated/imported (S47-003)"""

    total: int
    threshold: int
    items: list[AdminTaskReviewItem] = Field(default_factory=list)


class TaskModerateRequest(BaseModel):
    """Действие модератора над задачей (S47-003)"""

    action: ModerationAction
    #: Обязателен для return_to_revision, до 1000 символов
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validate_comment(self) -> "TaskModerateRequest":
        if self.comment is not None:
            self.comment = self.comment.strip()
        if self.action == "return_to_revision" and not self.comment:
            raise ValueError("Комментарий обязателен при возврате в доработку")
        if self.comment and len(self.comment) > 1000:
            raise ValueError("Комментарий не должен превышать 1000 символов")
        return self


class TaskModerateResponse(BaseModel):
    """Результат действия модератора (S47-003)"""

    id: UUID
    title: str
    action: ModerationAction
    source: str
    is_active: bool
    moderation_comment: str | None = None
