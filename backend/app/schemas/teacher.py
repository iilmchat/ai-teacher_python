"""
Схемы для Teacher Console (S15).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.task import TaskDifficulty, TaskStatus
from app.models.user import UserLevel


class TeacherStudentItem(BaseModel):
    """Ученик с агрегатами прогресса"""

    id: UUID
    email: EmailStr
    username: str
    level: UserLevel
    completed_tasks: int = 0
    attempts: int = 0
    last_active: datetime

    model_config = {"from_attributes": True}


class TeacherStudentList(BaseModel):
    """Список учеников"""

    total: int
    items: list[TeacherStudentItem]


class TeacherProgressItem(BaseModel):
    """Прогресс ученика по одной задаче"""

    task_id: UUID
    title: str
    difficulty: TaskDifficulty
    status: TaskStatus
    attempts: int
    completed_at: datetime | None = None


class TeacherStudentDetail(BaseModel):
    """Карточка ученика для преподавателя"""

    student: TeacherStudentItem
    total_tasks: int
    completed: int
    in_progress: int
    completion_rate: float
    items: list[TeacherProgressItem] = Field(default_factory=list)


class TeacherTaskItem(BaseModel):
    """Задача в таблице преподавателя (включая неактивные)"""

    id: UUID
    title: str
    difficulty: TaskDifficulty
    category: str
    tags: list[str] = Field(default_factory=list)
    test_cases_count: int
    hints_count: int
    is_active: bool
    created_at: datetime


class TeacherTaskList(BaseModel):
    """Список задач для преподавателя"""

    total: int
    items: list[TeacherTaskItem]
