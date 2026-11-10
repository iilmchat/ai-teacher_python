"""
Достижения, статистика и уведомления (S17-001…S17-004).
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models.chat import ChatMessage, ChatSession
from app.models.engagement import Achievement, Notification, UserAchievement
from app.models.task import Task, TaskDifficulty, TaskStatus, UserTaskProgress

#: Часовой пояс ученика для серии дней (UTC+3)
STREAK_TIMEZONE_OFFSET = timedelta(hours=3)


async def completed_dates(db: AsyncSession, user_id: UUID) -> list[datetime]:
    """Даты завершений (UTC+3), по одной на день, по возрастанию"""
    result = await db.execute(
        select(UserTaskProgress.completed_at).where(
            UserTaskProgress.user_id == user_id,
            UserTaskProgress.status == TaskStatus.COMPLETED,
            UserTaskProgress.completed_at.is_not(None),
        )
    )
    days = {
        (row[0] + STREAK_TIMEZONE_OFFSET).date()
        for row in result.all()
        if row[0] is not None
    }
    return [datetime.combine(day, datetime.min.time()) for day in sorted(days)]


def max_streak(dates: list[datetime]) -> int:
    """Максимальная серия подряд идущих дней"""
    best = 0
    current = 0
    previous = None
    for value in dates:
        day = value.date()
        if previous is not None and (day - previous).days == 1:
            current += 1
        else:
            current = 1
        best = max(best, current)
        previous = day
    return best


async def current_streak(db: AsyncSession, user_id: UUID) -> int:
    """Серия, заканчивающаяся сегодня или вчера (UTC+3)"""
    dates = await completed_dates(db, user_id)
    if not dates:
        return 0
    today = (datetime.utcnow() + STREAK_TIMEZONE_OFFSET).date()
    days = {value.date() for value in dates}
    if today not in days and (today - timedelta(days=1)) not in days:
        return 0
    streak = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def _completed_count(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(UserTaskProgress)
        .where(
            UserTaskProgress.user_id == user_id,
            UserTaskProgress.status == TaskStatus.COMPLETED,
        )
    )
    return int(result.scalar_one())


async def _completed_for_difficulty(
    db: AsyncSession, user_id: UUID, difficulty: TaskDifficulty
) -> tuple[int, int]:
    """(сколько задач сложности решено, сколько всего активных)"""
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Task)
                .where(Task.is_active.is_(True), Task.difficulty == difficulty)
            )
        ).scalar_one()
    )
    done = int(
        (
            await db.execute(
                select(func.count(func.distinct(UserTaskProgress.task_id)))
                .select_from(UserTaskProgress)
                .join(Task, Task.id == UserTaskProgress.task_id)
                .where(
                    UserTaskProgress.user_id == user_id,
                    UserTaskProgress.status == TaskStatus.COMPLETED,
                    Task.is_active.is_(True),
                    Task.difficulty == difficulty,
                )
            )
        ).scalar_one()
    )
    return done, total


async def evaluate_achievements(
    db: AsyncSession, user_id: UUID
) -> list[Achievement]:
    """Выдать новые достижения и уведомления; вернуть только новые"""
    earned = set(
        (
            await db.execute(
                select(UserAchievement.code).where(
                    UserAchievement.user_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    candidates: list[str] = []
    completed = await _completed_count(db, user_id)
    if completed >= 1:
        candidates.append("first_task")
    if completed >= 10:
        candidates.append("ten_tasks")
    if await current_streak(db, user_id) >= 3:
        candidates.append("streak_3")
    for difficulty in TaskDifficulty:
        done, total = await _completed_for_difficulty(db, user_id, difficulty)
        if total > 0 and done >= total:
            candidates.append(f"all_{difficulty.value}")

    new_codes = [code for code in candidates if code not in earned]
    if not new_codes:
        return []

    result = await db.execute(
        select(Achievement).where(Achievement.code.in_(new_codes))
    )
    achievements = list(result.scalars().all())
    now = datetime.utcnow()
    for achievement in achievements:
        db.add(
            UserAchievement(
                user_id=user_id, code=achievement.code, earned_at=now
            )
        )
        db.add(
            Notification(
                user_id=user_id,
                type="achievement",
                payload={
                    "achievement": achievement.code,
                    "title": achievement.title,
                    "icon": achievement.icon,
                },
            )
        )
    await db.commit()
    return achievements


async def list_achievements(
    db: AsyncSession, user_id: UUID
) -> list[tuple[Achievement, datetime]]:
    """Все полученные достижения с датой"""
    result = await db.execute(
        select(Achievement, UserAchievement.earned_at)
        .join(UserAchievement, UserAchievement.code == Achievement.code)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.earned_at.desc())
    )
    rows = result.all()
    return [(row[0], row[1]) for row in rows]


async def stats(db: AsyncSession, user_id: UUID) -> dict[str, int | float]:
    """Личная статистика ученика"""
    completed = await _completed_count(db, user_id)
    attempts = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(UserTaskProgress.attempts), 0)).where(
                    UserTaskProgress.user_id == user_id
                )
            )
        ).scalar_one()
    )
    sessions = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ChatSession)
                .where(ChatSession.user_id == user_id)
            )
        ).scalar_one()
    )
    messages = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ChatMessage)
                .join(ChatSession, ChatSession.id == ChatMessage.session_id)
                .where(ChatSession.user_id == user_id)
            )
        ).scalar_one()
    )
    achievements = int(
        (
            await db.execute(
                select(func.count())
                .select_from(UserAchievement)
                .where(UserAchievement.user_id == user_id)
            )
        ).scalar_one()
    )
    return {
        "solved": completed,
        "attempts": attempts,
        "avg_attempts": round(attempts / completed, 2) if completed else 0.0,
        "streak_days": await current_streak(db, user_id),
        "achievements_count": achievements,
        "chat_sessions": sessions,
        "chat_messages": messages,
    }


# --- Уведомления --------------------------------------------------------


async def create_assignment_notifications(
    db: AsyncSession,
    user_ids: list[UUID],
    *,
    classroom_id: UUID,
    classroom_name: str,
    assignment_id: UUID,
    task_id: UUID,
    task_title: str,
    due_at: datetime | None,
) -> int:
    """Уведомить учеников о новом назначении (D-007: безопасная ссылка)."""
    for user_id in user_ids:
        db.add(
            Notification(
                user_id=user_id,
                type="assignment",
                payload={
                    "classroom_id": str(classroom_id),
                    "classroom_name": classroom_name,
                    "assignment_id": str(assignment_id),
                    "task_id": str(task_id),
                    "title": task_title,
                    "due_at": due_at.isoformat() if due_at else None,
                    "link": "/assignments",
                },
            )
        )
    await db.commit()
    return len(user_ids)


async def create_feedback_notification(
    db: AsyncSession,
    user_id: UUID,
    *,
    attempt_id: UUID,
    task_id: UUID,
    task_title: str,
    teacher_name: str,
) -> None:
    """Уведомить ученика о комментарии учителя к попытке (S46-002)"""
    db.add(
        Notification(
            user_id=user_id,
            type="attempt_feedback",
            payload={
                "attempt_id": str(attempt_id),
                "task_id": str(task_id),
                "title": task_title,
                "teacher": teacher_name,
                "link": f"/tasks/{task_id}",
            },
        )
    )
    await db.commit()


async def create_announcement_notifications(
    db: AsyncSession,
    user_ids: list[UUID],
    *,
    classroom_id: UUID,
    classroom_name: str,
    announcement_id: UUID,
    title: str,
) -> int:
    """Уведомить учеников класса об объявлении (S46-006)"""
    for user_id in user_ids:
        db.add(
            Notification(
                user_id=user_id,
                type="announcement",
                payload={
                    "classroom_id": str(classroom_id),
                    "classroom_name": classroom_name,
                    "announcement_id": str(announcement_id),
                    "title": title,
                    "link": f"/classrooms/{classroom_id}",
                },
            )
        )
    await db.commit()
    return len(user_ids)


async def list_notifications(
    db: AsyncSession,
    user_id: UUID,
    unread_only: bool = False,
    notification_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Notification], int]:
    """Уведомления (с пагинацией S19-004) и число непрочитанных."""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if notification_type:
        query = query.where(Notification.type == notification_type)
    result = await db.execute(
        query.order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = list(result.scalars().all())
    unread = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
        ).scalar_one()
    )
    return notifications, unread


async def mark_read(
    db: AsyncSession, user_id: UUID, notification_id: UUID
) -> Notification:
    """Отметить уведомление прочитанным"""
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotFoundError("Уведомление не найдено")
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        await db.commit()
        await db.refresh(notification)
    return notification


async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
    """Отметить все непрочитанные уведомления одним UPDATE (S47-005)."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.utcnow())
        .returning(Notification.id)
    )
    updated = len(result.scalars().all())
    await db.commit()
    return updated


async def sync_deadline_notifications(db: AsyncSession, user_id: UUID) -> int:
    """Создать напоминания о дедлайнах по личным настройкам (S45-004)"""
    from app.models.classroom import Assignment, Classroom, ClassroomMember
    from app.models.user import User
    from app.services.notification_prefs import notification_preferences

    user = await db.get(User, user_id)
    prefs = notification_preferences(user.settings if user else None)
    if not prefs["deadline_notifications"]:
        return 0

    threshold = datetime.utcnow() + timedelta(days=prefs["deadline_days"])
    result = await db.execute(
        select(Assignment, Task, Classroom)
        .join(Classroom, Classroom.id == Assignment.classroom_id)
        .join(Task, Task.id == Assignment.task_id)
        .join(
            ClassroomMember,
            (ClassroomMember.classroom_id == Classroom.id)
            & (ClassroomMember.user_id == user_id),
        )
        .where(
            Assignment.due_at.is_not(None),
            Assignment.due_at <= threshold,
            Assignment.due_at >= datetime.utcnow(),
        )
    )
    existing_result = await db.execute(
        select(Notification.payload).where(
            Notification.user_id == user_id,
            Notification.type == "deadline",
        )
    )
    existing_ids = {
        str(payload.get("assignment_id"))
        for payload in existing_result.scalars().all()
        if isinstance(payload, dict)
    }
    progress = {
        row.task_id: row.status
        for row in (
            await db.execute(
                select(UserTaskProgress).where(
                    UserTaskProgress.user_id == user_id
                )
            )
        )
        .scalars()
        .all()
    }
    created = 0
    for assignment, task, classroom in result.all():
        if progress.get(task.id) == TaskStatus.COMPLETED:
            continue
        if str(assignment.id) in existing_ids:
            continue
        db.add(
            Notification(
                user_id=user_id,
                type="deadline",
                payload={
                    "assignment_id": str(assignment.id),
                    "classroom_id": str(classroom.id),
                    "classroom_name": classroom.name,
                    "task_id": str(task.id),
                    "title": task.title,
                    "due_at": assignment.due_at.isoformat()
                    if assignment.due_at
                    else None,
                    "link": "/assignments",
                },
            )
        )
        created += 1
    if created:
        await db.commit()
    return created
