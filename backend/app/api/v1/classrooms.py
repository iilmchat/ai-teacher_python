"""
Classrooms API (S16): классы, вступление, назначения, прогресс класса.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.database import get_db
from app.errors import ValidationError
from app.models.classroom import Classroom
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.classroom import (
    AnnouncementCreate,
    AnnouncementItem,
    AnnouncementList,
    AssignmentAnalytics,
    AssignmentAnalyticsStudent,
    AssignmentAttemptBucket,
    AssignmentCreate,
    AssignmentItem,
    AssignmentList,
    AssignmentUpdate,
    BulkAssignmentRequest,
    BulkAssignmentResult,
    BulkMembersAddRequest,
    BulkMembersAddResult,
    BulkMembersRemoveRequest,
    BulkMembersRemoveResult,
    ClassProgress,
    ClassroomCreate,
    ClassroomDetail,
    ClassroomList,
    ClassroomMemberItem,
    ClassroomResponse,
    GradebookCell,
    GradebookResponse,
    JoinClassroomRequest,
    MyAssignment,
    MyAssignmentList,
    ProblemTask,
    ProgressCell,
    ProgressStudent,
    ProgressTask,
    TemplateApplyRequest,
)
from app.services.audit_service import record_audit
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
    payload: ClassroomCreate,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> ClassroomResponse:
    """Создать класс (teacher/admin)"""
    service = ClassroomService(db)
    classroom = await service.create_classroom(current_user, payload.name)
    await record_audit(
        db,
        actor=current_user,
        action="classroom.created",
        entity_type="classroom",
        entity_id=classroom.id,
        payload={"name": classroom.name},
        request=request,
    )
    return _classroom_response(classroom, await service.members_count(classroom.id))


@router.get("/classrooms", response_model=ClassroomList)
async def list_classrooms(
    current_user: CurrentUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
) -> ClassroomList:
    """Классы текущего пользователя (S19-004: один запрос + пагинация)"""
    service = ClassroomService(db)
    rows = await service.list_for_user_with_counts(
        current_user, skip=skip, limit=limit
    )
    items = [
        _classroom_response(classroom, members_count)
        for classroom, members_count in rows
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
    # Участники читаются отдельным запросом ниже: selectinload здесь не нужен
    classroom = await service.get_for_user(classroom_id, current_user)
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


@router.post(
    "/classrooms/{classroom_id}/members/bulk",
    response_model=BulkMembersAddResult,
)
async def add_members_bulk(
    classroom_id: UUID,
    payload: BulkMembersAddRequest,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> BulkMembersAddResult:
    """Добавить учеников списком логинов (S46-005), только владелец."""
    added, skipped, unknown = await ClassroomService(db).add_members_bulk(
        classroom_id, current_user, payload.usernames
    )
    await record_audit(
        db,
        actor=current_user,
        action="classroom.members_bulk_added",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={
            "added": len(added),
            "skipped": len(skipped),
            "unknown": len(unknown),
        },
        request=request,
    )
    return BulkMembersAddResult(
        added=added, skipped=skipped, unknown=unknown
    )


@router.delete(
    "/classrooms/{classroom_id}/members/bulk",
    response_model=BulkMembersRemoveResult,
)
async def remove_members_bulk(
    classroom_id: UUID,
    payload: BulkMembersRemoveRequest,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> BulkMembersRemoveResult:
    """Снять выбранных учеников (S46-005), только владелец."""
    removed, skipped = await ClassroomService(db).remove_members_bulk(
        classroom_id, current_user, payload.user_ids
    )
    await record_audit(
        db,
        actor=current_user,
        action="classroom.members_bulk_removed",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={"removed": len(removed), "skipped": len(skipped)},
        request=request,
    )
    return BulkMembersRemoveResult(removed=removed, skipped=skipped)


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
    request: Request,
) -> AssignmentItem:
    """Назначить задачу классу"""
    service = ClassroomService(db)
    assignment = await service.add_assignment(
        classroom_id, current_user, payload.task_id, payload.due_at
    )
    await record_audit(
        db,
        actor=current_user,
        action="assignment.created",
        entity_type="assignment",
        entity_id=assignment.id,
        payload={
            "classroom_id": str(classroom_id),
            "task_id": str(assignment.task_id),
        },
        request=request,
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


@router.patch(
    "/classrooms/{classroom_id}/assignments/{assignment_id}",
    response_model=AssignmentItem,
)
async def update_assignment(
    classroom_id: UUID,
    assignment_id: UUID,
    payload: AssignmentUpdate,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> AssignmentItem:
    """Перенести срок назначения (S46-004), только владелец."""
    service = ClassroomService(db)
    assignment, task = await service.update_assignment(
        classroom_id, assignment_id, current_user, payload.due_at
    )
    await record_audit(
        db,
        actor=current_user,
        action="assignment.updated",
        entity_type="assignment",
        entity_id=assignment.id,
        payload={
            "classroom_id": str(classroom_id),
            "due_at": assignment.due_at.isoformat()
            if assignment.due_at is not None
            else None,
        },
        request=request,
    )
    items = await service.list_assignments(classroom_id, current_user)
    found = next(
        (item for item in items if item.assignment.id == assignment_id), None
    )
    return AssignmentItem(
        id=assignment.id,
        task_id=assignment.task_id,
        title=task.title,
        difficulty=task.difficulty,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
        completed_count=found.completed_count if found is not None else 0,
        total_members=found.total_members if found is not None else 0,
    )


@router.delete(
    "/classrooms/{classroom_id}/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_assignment(
    classroom_id: UUID,
    assignment_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> None:
    """Снять назначение (S46-004): прогресс сохраняется, уведомления — нет."""
    removed = await ClassroomService(db).delete_assignment(
        classroom_id, assignment_id, current_user
    )
    await record_audit(
        db,
        actor=current_user,
        action="assignment.deleted",
        entity_type="assignment",
        entity_id=assignment_id,
        payload={"classroom_id": str(classroom_id), "removed": removed},
        request=request,
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


@router.get(
    "/classrooms/{classroom_id}/assignments/{assignment_id}/analytics",
    response_model=AssignmentAnalytics,
)
async def assignment_analytics(
    classroom_id: UUID,
    assignment_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
    problem_threshold: int = Query(default=3, ge=0, le=100),
) -> AssignmentAnalytics:
    """Drill-down по назначению: кто как справился (S46-003)."""
    data = await ClassroomService(db).assignment_analytics(
        classroom_id,
        assignment_id,
        current_user,
        problem_threshold=problem_threshold,
    )
    return AssignmentAnalytics(
        assignment_id=data.assignment_id,
        task_id=data.task_id,
        task_title=data.task_title,
        due_at=data.due_at,
        total_students=data.total_students,
        completed=data.completed,
        in_progress=data.in_progress,
        not_started=data.not_started,
        overdue=data.overdue,
        attempts_total=data.attempts_total,
        attempts_distribution=[
            AssignmentAttemptBucket(
                attempts=bucket.attempts, students=bucket.students
            )
            for bucket in data.attempts_distribution
        ],
        problem_threshold=data.problem_threshold,
        problem_students=[
            AssignmentAnalyticsStudent(
                student_id=item.student_id,
                username=item.username,
                status=item.status,
                attempts=item.attempts,
                completed_at=item.completed_at,
                overdue=item.overdue,
            )
            for item in data.problem_students
        ],
        students=[
            AssignmentAnalyticsStudent(
                student_id=item.student_id,
                username=item.username,
                status=item.status,
                attempts=item.attempts,
                completed_at=item.completed_at,
                overdue=item.overdue,
            )
            for item in data.students
        ],
    )


@router.get("/classrooms/{classroom_id}/report")
async def classroom_report(
    classroom_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> Response:
    """CSV-отчёт класса (S26-002): матрица «ученик × задача», overdue, итоги.

    Доступ — только владелец класса (или админ); участник-ученик получает 403.
    """
    from app.services.class_report import build_class_report

    text, rows = await build_class_report(db, classroom_id, current_user)
    await record_audit(
        db,
        actor=current_user,
        action="classroom.report_exported",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={"rows": rows},
        request=request,
    )
    filename = f"classroom-{classroom_id}-report.csv"
    # utf-8-sig: Excel корректно открывает кириллицу в CSV
    return Response(
        content=text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Массовые назначения и журнал оценок (S28) ------------------------------


@router.post(
    "/classrooms/{classroom_id}/assignments/bulk",
    response_model=BulkAssignmentResult,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_assign(
    classroom_id: UUID,
    payload: BulkAssignmentRequest,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> BulkAssignmentResult:
    """Массовое назначение задач (S28-001), идемпотентно.

    Дубликаты и уже назначенные задачи не ошибка: они в `skipped`; неизвестные
    и неактивные — в `unknown`. Уведомления отправляются только по новым.
    """
    created, skipped, unknown = await ClassroomService(db).add_assignments_bulk(
        classroom_id, current_user, payload.task_ids, payload.due_at
    )
    await record_audit(
        db,
        actor=current_user,
        action="assignment.bulk_created",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={
            "created": len(created),
            "skipped": len(skipped),
            "unknown": len(unknown),
        },
        request=request,
    )
    return BulkAssignmentResult(created=created, skipped=skipped, unknown=unknown)


@router.post(
    "/classrooms/{classroom_id}/assignments/from-template",
    response_model=BulkAssignmentResult,
    status_code=status.HTTP_201_CREATED,
)
async def assign_from_template(
    classroom_id: UUID,
    payload: TemplateApplyRequest,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> BulkAssignmentResult:
    """Применить шаблон назначений к классу (S28-002)"""
    created, skipped, unknown = await ClassroomService(db).apply_template(
        classroom_id, current_user, payload.template_id, payload.due_at
    )
    await record_audit(
        db,
        actor=current_user,
        action="assignment.template_applied",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={"template_id": str(payload.template_id), "created": len(created)},
        request=request,
    )
    return BulkAssignmentResult(created=created, skipped=skipped, unknown=unknown)


@router.get(
    "/classrooms/{classroom_id}/gradebook", response_model=GradebookResponse
)
async def class_gradebook(
    classroom_id: UUID, current_user: TeacherUser, db: DbSession
) -> GradebookResponse:
    """Журнал оценок класса (S28-003): матрица + completed_at + overdue"""
    data = await ClassroomService(db).class_gradebook(classroom_id, current_user)
    return GradebookResponse(
        students=[
            ProgressStudent(id=student.id, username=student.username)
            for student in data.students
        ],
        tasks=[ProgressTask(id=task.id, title=task.title) for task in data.tasks],
        cells=[
            GradebookCell(
                student_id=cell.student_id,
                task_id=cell.task_id,
                status=cell.status,
                attempts=cell.attempts,
                completed_at=cell.completed_at,
            )
            for cell in data.cells
        ],
        completion_rate=data.completion_rate,
        overdue=data.overdue,
    )


@router.get("/classrooms/{classroom_id}/gradebook/csv")
async def class_gradebook_csv(
    classroom_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> Response:
    """Журнал оценок CSV (S28-003, формат — как отчёт класса S26-002)"""
    from app.services.class_report import build_class_report

    text, rows = await build_class_report(db, classroom_id, current_user)
    await record_audit(
        db,
        actor=current_user,
        action="gradebook.exported",
        entity_type="classroom",
        entity_id=classroom_id,
        payload={"rows": rows},
        request=request,
    )
    return Response(
        content=text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="gradebook-{classroom_id}.csv"'
            )
        },
    )


# --- Объявления класса (S46-006) -------------------------------------------


@router.get(
    "/classrooms/{classroom_id}/announcements",
    response_model=AnnouncementList,
)
async def list_announcements(
    classroom_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> AnnouncementList:
    """Объявления класса, новые сверху (видят все участники)."""
    rows = await ClassroomService(db).list_announcements(
        classroom_id, current_user, limit=limit
    )
    return AnnouncementList(
        items=[
            AnnouncementItem(
                id=announcement.id,
                classroom_id=announcement.classroom_id,
                author_id=announcement.author_id,
                author_name=author_name,
                title=announcement.title,
                body=announcement.body,
                created_at=announcement.created_at,
                can_delete=announcement.author_id == current_user.id,
            )
            for announcement, author_name in rows
        ]
    )


@router.post(
    "/classrooms/{classroom_id}/announcements",
    response_model=AnnouncementItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    classroom_id: UUID,
    payload: AnnouncementCreate,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> AnnouncementItem:
    """Опубликовать объявление (S46-006), только владелец класса.

    Публикация порождает in-app уведомление всем ученикам класса.
    """
    announcement = await ClassroomService(db).create_announcement(
        classroom_id, current_user, payload.title, payload.body
    )
    await record_audit(
        db,
        actor=current_user,
        action="announcement.created",
        entity_type="announcement",
        entity_id=announcement.id,
        payload={
            "classroom_id": str(classroom_id),
            "title_length": len(announcement.title),
        },
        request=request,
    )
    return AnnouncementItem(
        id=announcement.id,
        classroom_id=announcement.classroom_id,
        author_id=announcement.author_id,
        author_name=current_user.username,
        title=announcement.title,
        body=announcement.body,
        created_at=announcement.created_at,
        can_delete=True,
    )


@router.delete(
    "/classrooms/{classroom_id}/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_announcement(
    classroom_id: UUID,
    announcement_id: UUID,
    current_user: TeacherUser,
    db: DbSession,
    request: Request,
) -> None:
    """Удалить объявление: автор или владелец класса (S46-006)."""
    await ClassroomService(db).delete_announcement(
        classroom_id, announcement_id, current_user
    )
    await record_audit(
        db,
        actor=current_user,
        action="announcement.deleted",
        entity_type="announcement",
        entity_id=announcement_id,
        payload={"classroom_id": str(classroom_id)},
        request=request,
    )


@router.get("/me/announcements", response_model=AnnouncementList)
async def my_announcements(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> AnnouncementList:
    """Лента объявлений всех классов пользователя (S46-006)."""
    rows = await ClassroomService(db).announcements_for_user(
        current_user, limit=limit
    )
    return AnnouncementList(
        items=[
            AnnouncementItem(
                id=announcement.id,
                classroom_id=announcement.classroom_id,
                classroom_name=classroom_name,
                author_id=announcement.author_id,
                author_name=author_name,
                title=announcement.title,
                body=announcement.body,
                created_at=announcement.created_at,
                can_delete=announcement.author_id == current_user.id,
            )
            for announcement, author_name, classroom_name in rows
        ]
    )
