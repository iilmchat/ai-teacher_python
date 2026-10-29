"""
Classrooms API (S16): классы, вступление, назначения, прогресс класса.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.database import get_db
from app.errors import ValidationError
from app.models.classroom import Classroom
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.classroom import (
    AssignmentCreate,
    AssignmentItem,
    AssignmentList,
    ClassProgress,
    ClassroomCreate,
    ClassroomDetail,
    ClassroomList,
    ClassroomMemberItem,
    ClassroomResponse,
    JoinClassroomRequest,
    MyAssignment,
    MyAssignmentList,
    ProblemTask,
    ProgressCell,
    ProgressStudent,
    ProgressTask,
)
from app.services.classroom_service import ClassroomService

router = APIRouter(tags=["Classrooms"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
TeacherUser = Annotated[
    User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))
]


def _classroom_response(
    classroom: Classroom, members_count: int
) -> ClassroomResponse:
    return ClassroomResponse(
        id=classroom.id,
        name=classroom.name,
        owner_id=classroom.owner_id,
        join_code=classroom.join_code,
        created_at=classroom.created_at,
        members_count=members_count,
    )


@router.post(
    "/classrooms", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED
)
async def create_classroom(
    payload: ClassroomCreate, current_user: TeacherUser, db: DbSession
) -> ClassroomResponse:
    """Создать класс (teacher/admin)"""
    service = ClassroomService(db)
    classroom = await service.create_classroom(current_user, payload.name)
    return _classroom_response(classroom, await service.members_count(classroom.id))


@router.get("/classrooms", response_model=ClassroomList)
async def list_classrooms(
    current_user: CurrentUser, db: DbSession
) -> ClassroomList:
    """Классы текущего пользователя"""
    service = ClassroomService(db)
    items = [
        _classroom_response(classroom, await service.members_count(classroom.id))
        for classroom in await service.list_for_user(current_user)
    ]
    return ClassroomList(items=items)


@router.post("/classrooms/join", response_model=ClassroomResponse)
async def join_classroom(
    payload: JoinClassroomRequest, current_user: CurrentUser, db: DbSession
) -> ClassroomResponse:
    """Вступить в класс по коду"""
    service = ClassroomService(db)
    classroom = await service.join_by_code(current_user, payload.join_code)
    return _classroom_response(classroom, await service.members_count(classroom.id))


@router.get("/classrooms/{classroom_id}", response_model=ClassroomDetail)
async def get_classroom(
    classroom_id: UUID, current_user: CurrentUser, db: DbSession
) -> ClassroomDetail:
    """Класс с участниками"""
    service = ClassroomService(db)
    classroom = await service.get_for_user(
        classroom_id, current_user, with_members=True
    )
    member_rows = await service.get_members(classroom_id)
    users = {
        user.id: user
        for user in (
            await db.execute(
                select(User).where(User.id.in_([row.user_id for row in member_rows]))
            )
        )
        .scalars()
        .all()
    }
    members = [
        ClassroomMemberItem(
            user_id=member.user_id,
            username=users[member.user_id].username
            if member.user_id in users
            else "",
            role=member.role,
            joined_at=member.joined_at,
        )
        for member in member_rows
    ]
    base = _classroom_response(classroom, len(members))
    return ClassroomDetail(
        **base.model_dump(), members=members
    )


@router.post("/classrooms/{classroom_id}/join", response_model=ClassroomResponse)
async def join_classroom_by_id(
    classroom_id: UUID,
    payload: JoinClassroomRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ClassroomResponse:
    """Вступить в конкретный класс по коду (проверяет совпадение)"""
    service = ClassroomService(db)
    joined = await service.join_by_code(current_user, payload.join_code)
    if joined.id != classroom_id:
        raise ValidationError("Код принадлежит другому классу")
    return _classroom_response(joined, await service.members_count(joined.id))


@router.delete(
    "/classrooms/{classroom_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    classroom_id: UUID,
    user_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
) -> None:
    """Удалить участника класса (владелец)"""
    await ClassroomService(db).remove_member(classroom_id, user_id, current_user)


@router.post(
    "/classrooms/{classroom_id}/assignments",
    response_model=AssignmentItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    classroom_id: UUID,
    payload: AssignmentCreate,
    current_user: TeacherUser,
    db: DbSession,
) -> AssignmentItem:
    """Назначить задачу классу"""
    service = ClassroomService(db)
    assignment = await service.add_assignment(
        classroom_id, current_user, payload.task_id, payload.due_at
    )
    task = await db.get(Task, assignment.task_id)
    assert task is not None
    return AssignmentItem(
        id=assignment.id,
        task_id=assignment.task_id,
        title=task.title,
        difficulty=task.difficulty,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
    )


@router.get(
    "/classrooms/{classroom_id}/assignments", response_model=AssignmentList
)
async def list_assignments(
    classroom_id: UUID, current_user: CurrentUser, db: DbSession
) -> AssignmentList:
    """Назначения класса со счётчиками выполнения"""
    rows = await ClassroomService(db).list_assignments(classroom_id, current_user)
    return AssignmentList(
        items=[
            AssignmentItem(
                id=row.assignment.id,
                task_id=row.task.id,
                title=row.task.title,
                difficulty=row.task.difficulty,
                due_at=row.assignment.due_at,
                created_at=row.assignment.created_at,
                completed_count=row.completed_count,
                total_members=row.total_members,
            )
            for row in rows
        ]
    )


@router.get("/me/assignments", response_model=MyAssignmentList)
async def my_assignments(
    current_user: CurrentUser, db: DbSession
) -> MyAssignmentList:
    """«Мои задания» по всем классам"""
    rows = await ClassroomService(db).my_assignments(current_user)
    return MyAssignmentList(
        items=[
            MyAssignment(
                id=row.assignment.id,
                classroom_id=row.classroom.id,
                classroom_name=row.classroom.name,
                task_id=row.task.id,
                title=row.task.title,
                difficulty=row.task.difficulty,
                due_at=row.assignment.due_at,
                status=row.status,
                overdue=row.overdue,
            )
            for row in rows
        ]
    )


@router.get("/classrooms/{classroom_id}/progress", response_model=ClassProgress)
async def class_progress(
    classroom_id: UUID, current_user: TeacherUser, db: DbSession
) -> ClassProgress:
    """Матрица прогресса класса"""
    data = await ClassroomService(db).class_progress(classroom_id, current_user)
    return ClassProgress(
        students=[
            ProgressStudent(id=student.id, username=student.username)
            for student in data.students
        ],
        tasks=[ProgressTask(id=task.id, title=task.title) for task in data.tasks],
        cells=[
            ProgressCell(
                student_id=cell.student_id,
                task_id=cell.task_id,
                status=cell.status,
                attempts=cell.attempts,
            )
            for cell in data.cells
        ],
        completion_rate=data.completion_rate,
        problem_tasks=[
            ProblemTask(
                task_id=task.task_id,
                title=task.title,
                attempts=task.attempts,
                completed=task.completed,
            )
            for task in data.problem_tasks
        ],
    )
