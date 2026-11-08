"""
Схемы задач и прогресса (S7-002).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.task import TaskDifficulty, TaskStatus

MAX_TEST_CASES = 50
MAX_TAGS = 10


def _normalize_tags(value: list[str] | None) -> list[str] | None:
    """Теги — в нижний регистр, без дублей и пустых значений"""
    if value is None:
        return None
    result: list[str] = []
    for tag in value:
        normalized = tag.strip().lower()
        if normalized and normalized not in result:
            result.append(normalized[:30])
    if len(result) > MAX_TAGS:
        raise ValueError(f"Не больше {MAX_TAGS} тегов")
    return result


class TestCase(BaseModel):
    """Один тест-кейс задачи"""

    input: str = Field(default="", max_length=10_000, description="Данные для input()")
    expected_output: str = Field(..., max_length=10_000)
    description: str | None = Field(default=None, max_length=255)


class TaskCreate(BaseModel):
    """Создание задачи преподавателем"""

    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    difficulty: TaskDifficulty = TaskDifficulty.EASY
    category: str = Field(default="general", max_length=100)
    test_cases: list[TestCase] = Field(..., min_length=1, max_length=MAX_TEST_CASES)
    hints: list[str] = Field(default_factory=list, max_length=20)
    solution_template: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)

    @field_validator("test_cases")
    @classmethod
    def at_least_one_case(cls, value: list[TestCase]) -> list[TestCase]:
        if not value:
            raise ValueError("Нужен хотя бы один тест-кейс")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value) or []


class TaskUpdate(BaseModel):
    """Частичное обновление задачи"""

    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, min_length=10)
    difficulty: TaskDifficulty | None = None
    category: str | None = Field(None, max_length=100)
    test_cases: list[TestCase] | None = Field(None, max_length=MAX_TEST_CASES)
    hints: list[str] | None = Field(None, max_length=20)
    solution_template: str | None = None
    tags: list[str] | None = Field(None, max_length=MAX_TAGS)
    is_active: bool | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tags(value)


class TaskListItem(BaseModel):
    """Задача в списке (без решений и тестов)"""

    id: UUID
    title: str
    difficulty: TaskDifficulty
    category: str
    hints_count: int
    status: TaskStatus
    tags: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TaskDetail(BaseModel):
    """Полная карточка задачи для ученика"""

    id: UUID
    title: str
    description: str
    difficulty: TaskDifficulty
    category: str
    hints: list[str]
    solution_template: str | None
    test_cases_count: int
    status: TaskStatus
    attempts: int
    tags: list[str] = Field(default_factory=list)
    #: Сохранённый черновик решения (S42-003); `None`, если черновика нет
    draft_code: str | None = None
    draft_updated_at: datetime | None = None


class TaskAdminDetail(TaskDetail):
    """Карточка задачи для преподавателя (с тест-кейсами)"""

    test_cases: list[TestCase]
    is_active: bool


class DraftRequest(BaseModel):
    """Сохранение черновика решения (S42-003)"""

    code: str = Field(..., max_length=20_000)


class DraftStatus(BaseModel):
    """Состояние черновика (S42-003)"""

    #: Есть ли сохранённый черновик
    has_draft: bool = False
    #: Когда черновик сохранён
    updated_at: datetime | None = None


class SolutionCode(BaseModel):
    """Код решения (общая часть для отправки и пробной проверки)"""

    code: str = Field(..., min_length=1, max_length=20_000)


class SubmitRequest(SolutionCode):
    """Отправка решения на проверку (попытка засчитывается)"""


class CheckRequest(SolutionCode):
    """Пробная проверка решения (S42-001): попытка не засчитывается"""


class TestCaseResult(BaseModel):
    """Результат одного тест-кейса"""

    index: int
    passed: bool
    description: str | None = None
    input: str
    expected_output: str
    actual_output: str
    error: str | None = None


class SubmitResponse(BaseModel):
    """Результат проверки решения"""

    passed: bool
    passed_count: int
    total_count: int
    attempts: int
    status: TaskStatus
    results: list[TestCaseResult]
    message: str
    #: `True` для пробной проверки (S42-001): попытка не засчитывается
    practice: bool = False


class AttemptItem(BaseModel):
    """Попытка ученика по задаче (S42-002)"""

    id: UUID
    task_id: UUID
    passed: bool
    passed_count: int
    total_count: int
    created_at: datetime
    #: Комментарии учителей (S46-002), новые сверху
    feedback: list["AttemptFeedbackItem"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AttemptFeedbackItem(BaseModel):
    """Комментарий учителя к попытке (S46-002)"""

    id: UUID
    comment: str
    teacher_name: str
    created_at: datetime


class AttemptDetail(AttemptItem):
    """Попытка с кодом и разбором по кейсам"""

    code: str
    results: list[TestCaseResult]


class AttemptList(BaseModel):
    """История попыток постранично"""

    items: list[AttemptItem] = Field(default_factory=list)
    total: int = 0


class RecommendedTask(BaseModel):
    """Рекомендуемая задача с объяснением выбора (S42-005)"""

    id: UUID
    title: str
    difficulty: TaskDifficulty
    category: str
    tags: list[str] = Field(default_factory=list)
    #: Машиночитаемая причина: `continue` | `same_topic` | `easier` |
    #: `next_step` | `starter`
    reason: str
    #: Пояснение для ученика (текст на русском)
    reason_text: str


class RecommendedTaskList(BaseModel):
    """Список рекомендаций"""

    items: list[RecommendedTask] = Field(default_factory=list)


class ProgressItem(BaseModel):
    """Прогресс по одной задаче"""

    task_id: UUID
    title: str
    difficulty: TaskDifficulty
    status: TaskStatus
    attempts: int
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ProgressSummary(BaseModel):
    """Сводка прогресса ученика"""

    total_tasks: int
    completed: int
    in_progress: int
    not_started: int
    completion_rate: float
    by_difficulty: dict[str, dict[str, int]]
    items: list[ProgressItem]


class TaskStatsResponse(BaseModel):
    """Статистика по задачам для дашборда"""

    total_tasks: int
    by_difficulty: dict[str, int]
    by_category: dict[str, int]
    total_attempts: int
    total_completions: int


class HintResponse(BaseModel):
    """Подсказка по задаче"""

    index: int
    hint: str
    total: int


class TestRunOutcome(BaseModel):
    """Технический результат прогона тестов (для сервиса)"""

    passed: bool
    passed_count: int
    total_count: int
    results: list[TestCaseResult]
    all_violations: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


# --- Импорт, экспорт, генерация, версии (S14) ---------------------------


class TaskImportRequest(BaseModel):
    """Импорт задач: массив объектов в формате TaskCreate"""

    tasks: list[dict[str, Any]] = Field(..., min_length=1, max_length=100)


class TaskImportError(BaseModel):
    """Ошибка одной записи импорта"""

    index: int
    title: str | None = None
    message: str


class TaskImportContent(BaseModel):
    """Текст файла для предпросмотра импорта"""

    content: str = Field(..., min_length=1, max_length=2_000_000)


class TaskImportPreview(BaseModel):
    """Предпросмотр файла: сколько задач валидны, где ошибки"""

    tasks: int
    errors: list[TaskImportError] = Field(default_factory=list)


class TaskImportResponse(BaseModel):
    """Отчёт импорта: созданные, пропущенные, ошибки"""

    created: int
    skipped: int
    errors: list[TaskImportError] = Field(default_factory=list)


class TaskExportItem(TaskCreate):
    """Задача в выгрузке (полный формат для повторного импорта)"""

    id: UUID


class TaskGenerateRequest(BaseModel):
    """Генерация задач через LLM"""

    topic: str = Field(..., min_length=3, max_length=200)
    difficulty: TaskDifficulty = TaskDifficulty.EASY
    count: int = Field(default=1, ge=1, le=5)


class TaskGenerateError(BaseModel):
    """Причина, по которой сгенерированная задача не сохранена"""

    title: str | None = None
    reason: str


class TaskGenerateResponse(BaseModel):
    """Результат генерации: сохранённые задачи и отказы"""

    created: list[TaskAdminDetail] = Field(default_factory=list)
    rejected: list[TaskGenerateError] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


class TaskVersionItem(BaseModel):
    """Версия задачи в истории"""

    id: UUID
    version: int
    title: str
    test_cases_count: int
    solution_template: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskVersionList(BaseModel):
    """История версий задачи"""

    items: list[TaskVersionItem]


class CategoriesResponse(BaseModel):
    """Список категорий задач"""

    categories: list[str]
