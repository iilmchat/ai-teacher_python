"""Схемы классов и назначений (S16)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskDifficulty, TaskStatus


class ClassroomCreate(BaseModel):
    """Создание класса"""

    name: str = Field(..., min_length=3, max_length=100)


class ClassroomResponse(BaseModel):
    """Класс в списке"""

    id: UUID
    name: str
    owner_id: UUID
    join_code: str
    created_at: datetime
    members_count: int = 0


class ClassroomList(BaseModel):
    items: list[ClassroomResponse]


class ClassroomMemberItem(BaseModel):
    """Участник класса (email одноклассникам не раскрываем)"""

    user_id: UUID
    username: str
    role: str
    joined_at: datetime


class ClassroomDetail(ClassroomResponse):
    """Класс с участниками"""

    members: list[ClassroomMemberItem] = Field(default_factory=list)


class JoinClassroomRequest(BaseModel):
    """Вступление в класс по коду"""

    join_code: str = Field(..., min_length=4, max_length=12)


class AssignmentCreate(BaseModel):
    """Назначение задачи классу"""

    task_id: UUID
    due_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    """Перенос срока назначения (S46-004)"""

    due_at: datetime | None = None


class AssignmentItem(BaseModel):
    """Назначение в классе"""

    id: UUID
    task_id: UUID
    title: str
    difficulty: TaskDifficulty
    due_at: datetime | None
    created_at: datetime
    completed_count: int = 0
    total_members: int = 0


class AssignmentList(BaseModel):
    items: list[AssignmentItem]


class MyAssignment(BaseModel):
    """Задание ученика"""

    id: UUID
    classroom_id: UUID
    classroom_name: str
    task_id: UUID
    title: str
    difficulty: TaskDifficulty
    due_at: datetime | None
    status: TaskStatus
    overdue: bool


class MyAssignmentList(BaseModel):
    items: list[MyAssignment]


class ProgressStudent(BaseModel):
    id: UUID
    username: str


class ProgressTask(BaseModel):
    id: UUID
    title: str


class ProgressCell(BaseModel):
    student_id: UUID
    task_id: UUID
    status: TaskStatus
    attempts: int


class ProblemTask(BaseModel):
    task_id: UUID
    title: str
    attempts: int
    completed: int


class ClassProgress(BaseModel):
    students: list[ProgressStudent]
    tasks: list[ProgressTask]
    cells: list[ProgressCell]
    completion_rate: float
    problem_tasks: list[ProblemTask] = Field(default_factory=list)


class AssignmentAnalyticsStudent(BaseModel):
    """Ученик в drill-down по назначению (S46-003)"""

    student_id: UUID
    username: str
    status: TaskStatus
    attempts: int
    completed_at: datetime | None = None
    overdue: bool = False


class AssignmentAttemptBucket(BaseModel):
    """Сколько учеников сделали столько-то попыток"""

    attempts: int
    students: int


class AssignmentAnalytics(BaseModel):
    """Аналитика одного назначения: кто как справился (S46-003)"""

    assignment_id: UUID
    task_id: UUID
    task_title: str
    due_at: datetime | None = None
    total_students: int
    completed: int
    in_progress: int
    not_started: int
    overdue: int
    attempts_total: int
    attempts_distribution: list[AssignmentAttemptBucket] = Field(
        default_factory=list
    )
    problem_threshold: int
    problem_students: list[AssignmentAnalyticsStudent] = Field(
        default_factory=list
    )
    students: list[AssignmentAnalyticsStudent] = Field(default_factory=list)

class BulkAssignmentRequest(BaseModel):
    """Массовое назначение задач классу (S28-001)"""

    task_ids: list[UUID] = Field(..., min_length=1, max_length=50)
    due_at: datetime | None = None


class BulkAssignmentResult(BaseModel):
    """Итог массового назначения: созданные/пропущенные/неизвестные задачи"""

    created: list[UUID] = Field(default_factory=list)
    skipped: list[UUID] = Field(default_factory=list)
    unknown: list[UUID] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    """Создание шаблона назначений учителя (S28-002)"""

    name: str = Field(..., min_length=1, max_length=120)
    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class TemplateItem(BaseModel):
    """Шаблон назначений"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    task_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class TemplateList(BaseModel):
    items: list[TemplateItem]
    total: int


class GradebookCell(BaseModel):
    """Ячейка журнала оценок (S28-003)"""

    student_id: UUID
    task_id: UUID
    status: TaskStatus
    attempts: int
    completed_at: datetime | None = None


class GradebookResponse(BaseModel):
    """Журнал оценок: матрица ученик × задача + сводка"""

    students: list[ProgressStudent]
    tasks: list[ProgressTask]
    cells: list[GradebookCell]
    completion_rate: float
    overdue: int


class TemplateApplyRequest(BaseModel):
    """Применение шаблона к классу (S28-002)"""

    template_id: UUID
    due_at: datetime | None = None
