"""Отчёт класса CSV (S26-002).

Матрица «ученик × задача»: статус, попытки, дата завершения, overdue.
Доступ — владелец класса (или админ); участник-ученик получает 403, как и
`/progress` (RULES §11.15 п. 4).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classroom import ClassroomRole
from app.models.task import TaskStatus, UserTaskProgress
from app.models.user import User
from app.services.classroom_service import ClassroomService

logger = structlog.get_logger(__name__)

REPORT_COLUMNS = [
    "student_id",
    "username",
    "task_id",
    "task_title",
    "status",
    "attempts",
    "completed_at",
    "due_at",
    "overdue",
]


async def build_class_report(
    db: AsyncSession, classroom_id: UUID, user: User
) -> tuple[str, int]:
    """CSV-отчёт класса: (текст, число строк)"""
    service = ClassroomService(db)
    classroom = await service.get_for_user(classroom_id, user)
    if classroom.owner_id != user.id and user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Отчёт доступен только владельцу класса",
        )

    assignments = await service.list_assignments(classroom_id, user)
    members = await service.get_members(classroom_id)
    students = [
        member for member in members if member.role == ClassroomRole.STUDENT.value
    ]

    task_ids = [item.assignment.task_id for item in assignments]
    due_by_task = {
        item.assignment.task_id: item.assignment.due_at for item in assignments
    }
    title_by_task = {item.task.id: item.task.title for item in assignments}

    usernames: dict[UUID, str] = {}
    if students:
        rows = await db.execute(
            select(User.id, User.username).where(
                User.id.in_([member.user_id for member in students])
            )
        )
        for user_id, username in rows.all():
            usernames[user_id] = username

    progress: dict[tuple[UUID, UUID], UserTaskProgress] = {}
    if students and task_ids:
        rows = await db.execute(
            select(UserTaskProgress).where(
                UserTaskProgress.user_id.in_(
                    [member.user_id for member in students]
                ),
                UserTaskProgress.task_id.in_(task_ids),
            )
        )
        progress = {
            (item.user_id, item.task_id): item for item in rows.scalars().all()
        }

    now = datetime.utcnow()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=REPORT_COLUMNS, lineterminator="\r\n")
    writer.writeheader()

    row_count = 0
    overdue_total = 0
    for student in students:
        for task_id in task_ids:
            record = progress.get((student.user_id, task_id))
            task_status = record.status.value if record else TaskStatus.NOT_STARTED.value
            due_at = due_by_task.get(task_id)
            overdue = bool(
                due_at is not None
                and due_at < now
                and task_status != TaskStatus.COMPLETED.value
            )
            overdue_total += int(overdue)
            writer.writerow(
                {
                    "student_id": str(student.user_id),
                    "username": usernames.get(student.user_id, ""),
                    "task_id": str(task_id),
                    "task_title": title_by_task.get(task_id, ""),
                    "status": task_status,
                    "attempts": record.attempts if record else 0,
                    "completed_at": (
                        record.completed_at.isoformat()
                        if record and record.completed_at
                        else ""
                    ),
                    "due_at": due_at.isoformat() if due_at else "",
                    "overdue": "yes" if overdue else "no",
                }
            )
            row_count += 1

    summary: dict[str, Any] = {
        "student_id": "",
        "username": "ИТОГО",
        "task_id": "",
        "task_title": f"студентов={len(students)}, задач={len(task_ids)}",
        "status": "",
        "attempts": "",
        "completed_at": "",
        "due_at": "",
        "overdue": f"overdue={overdue_total}",
    }
    writer.writerow(summary)
    logger.info(
        "class_report_built",
        classroom_id=str(classroom_id),
        students=len(students),
        tasks=len(task_ids),
        rows=row_count,
    )
    return buffer.getvalue(), row_count


__all__ = ["REPORT_COLUMNS", "build_class_report"]
