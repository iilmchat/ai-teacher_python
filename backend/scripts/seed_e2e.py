"""E2E-фикстуры: учитель и класс с фиксированным кодом (S46).

Запускается Playwright webServer после миграций и seed задач. Идемпотентен:
повторный запуск не создаёт дублей. Пароль фиксированный — только для
изолированной БД `ai_teacher_e2e`, наружу этот скрипт не вызывается.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.database import async_session_factory  # noqa: E402
from app.models.classroom import (  # noqa: E402
    Classroom,
    ClassroomMember,
    ClassroomRole,
)
from app.models.user import User, UserRole  # noqa: E402

TEACHER_USERNAME = "e2e_teacher"
TEACHER_PASSWORD = "password123"
ADMIN_USERNAME = "e2e_admin"
ADMIN_PASSWORD = "password123"
CLASSROOM_NAME = "E2E класс 46"
JOIN_CODE = "E2E46"


async def seed() -> None:
    async with async_session_factory() as session:
        teacher = (
            await session.execute(
                select(User).where(User.username == TEACHER_USERNAME)
            )
        ).scalar_one_or_none()
        if teacher is None:
            teacher = User(
                email=f"{TEACHER_USERNAME}@example.com",
                username=TEACHER_USERNAME,
                hashed_password=hash_password(TEACHER_PASSWORD),
                role=UserRole.TEACHER,
            )
            session.add(teacher)
            await session.flush()

        admin = (
            await session.execute(
                select(User).where(User.username == ADMIN_USERNAME)
            )
        ).scalar_one_or_none()
        if admin is None:
            admin = User(
                email=f"{ADMIN_USERNAME}@example.com",
                username=ADMIN_USERNAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
            )
            session.add(admin)
            await session.flush()
        elif admin.role != UserRole.ADMIN:
            admin.role = UserRole.ADMIN

        classroom = (
            await session.execute(
                select(Classroom).where(Classroom.join_code == JOIN_CODE)
            )
        ).scalar_one_or_none()
        if classroom is None:
            classroom = Classroom(
                name=CLASSROOM_NAME,
                owner_id=teacher.id,
                join_code=JOIN_CODE,
            )
            session.add(classroom)
            await session.flush()
            session.add(
                ClassroomMember(
                    classroom_id=classroom.id,
                    user_id=teacher.id,
                    role=ClassroomRole.OWNER.value,
                )
            )

        await session.commit()
        print(
            f"E2E: учитель {TEACHER_USERNAME}, админ {ADMIN_USERNAME}, "
            f"класс {CLASSROOM_NAME} (код {JOIN_CODE}) готовы"
        )


if __name__ == "__main__":
    asyncio.run(seed())
