"""
Схемы задач и прогресса (S7-002).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.task import TaskDifficulty, TaskStatus

MAX_TEST_CASES = 50


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

    @field_validator("test_cases")
    @classmethod
    def at_least_one_case(cls, value: list[TestCase]) -> list[TestCase]:
        if not value:
            raise ValueError("Нужен хотя бы один тест-кейс")
        return value


class TaskUpdate(BaseModel):
    """Частичное обновление задачи"""

    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, min_length=10)
    difficulty: TaskDifficulty | None = None
    category: str | None = Field(None, max_length=100)
    test_cases: list[TestCase] | None = Field(None, max_length=MAX_TEST_CASES)
    hints: list[str] | None = Field(None, max_length=20)
    solution_template: str | None = None
    is_active: bool | None = None


class TaskListItem(BaseModel):
    """Задача в списке (без решений и тестов)"""

    id: UUID
    title: str
    difficulty: TaskDifficulty
    category: str
    hints_count: int
    status: TaskStatus

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


class TaskAdminDetail(TaskDetail):
    """Карточка задачи для преподавателя (с тест-кейсами)"""

    test_cases: list[TestCase]
    is_active: bool


class SubmitRequest(BaseModel):
    """Отправка решения на проверку"""

    code: str = Field(..., min_length=1, max_length=20_000)


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
