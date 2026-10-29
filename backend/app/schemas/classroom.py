"""Схемы классов и назначений (S16)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

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
    """Участник класса"""

    user_id: UUID
    username: str
    email: EmailStr
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
