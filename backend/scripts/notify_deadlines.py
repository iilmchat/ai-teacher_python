"""Напоминания о дедлайнах (S28-004) — CLI.

    python backend/scripts/notify_deadlines.py --dry-run
    python backend/scripts/notify_deadlines.py

Ищет назначения со сроком в ближайшие `NOTIFICATIONS_DEADLINE_HOURS` часов и
отправляет письма ученикам класса. Дедупликации отправок нет (повторный запуск
в окне пришлёт письмо ещё раз) — запускайте по cron раз в сутки.
Без `NOTIFICATIONS_EMAIL_ENABLED=true` письма только пишутся в лог.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import async_session_factory  # noqa: E402
from app.models.classroom import (  # noqa: E402
    Assignment,
    Classroom,
    ClassroomMember,
    ClassroomRole,
)
from app.models.task import Task  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.email import get_email_sender, send_assignment_email  # noqa: E402


async def notify(dry_run: bool) -> int:
    now = datetime.utcnow()
    horizon = now + timedelta(hours=settings.notifications_deadline_hours)
    sender = get_email_sender()
    sent = 0
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(Assignment, Task, Classroom)
                .join(Task, Task.id == Assignment.task_id)
                .join(Classroom, Classroom.id == Assignment.classroom_id)
                .where(
                    Assignment.due_at.is_not(None),
                    Assignment.due_at >= now,
                    Assignment.due_at <= horizon,
                )
            )
        ).all()
        print(f"assignments in window: {len(rows)}")
        for assignment, task, classroom in rows:
            members = (
                await db.execute(
                    select(ClassroomMember.user_id).where(
                        ClassroomMember.classroom_id == classroom.id,
                        ClassroomMember.role == ClassroomRole.STUDENT.value,
                    )
                )
            ).scalars().all()
            if not members:
                continue
            emails = (
                await db.execute(select(User.email).where(User.id.in_(members)))
            ).scalars().all()
            print(
                f"  {classroom.name}: {task.title} до {assignment.due_at:%Y-%m-%d %H:%M} "
                f"({len(emails)} учеников)"
            )
            if dry_run:
                sent += len(emails)
                continue
            for email in emails:
                ok = await send_assignment_email(
                    sender,
                    to=email,
                    classroom_name=classroom.name,
                    task_title=task.title,
                    due_at=assignment.due_at.isoformat() if assignment.due_at else None,
                )
                sent += int(ok)
    print(f"emails {'to send' if dry_run else 'sent'}: {sent}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Напоминания о дедлайнах (S28-004)")
    parser.add_argument("--dry-run", action="store_true", help="только показать")
    args = parser.parse_args(argv)
    return asyncio.run(notify(args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
