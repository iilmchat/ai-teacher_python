"""
Наполнение базы учебными задачами (S7-001, S14-002).

Запуск из `backend/`:

    python scripts/seed_tasks.py

Скрипт идемпотентен: задачи определяются по заголовку и не дублируются.
Те же данные используются при `SEED_ON_START=true`.
"""

import asyncio
import sys
from pathlib import Path

# Разрешаем импорт пакета app при запуске из backend/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.seed_tasks import TASKS  # noqa: E402
from app.db.database import async_session_factory  # noqa: E402
from app.services.seed_service import seed_tasks  # noqa: E402


async def seed() -> int:
    """Добавить задачи, которых ещё нет по заголовку"""
    async with async_session_factory() as session:
        return await seed_tasks(session)


if __name__ == "__main__":
    count = asyncio.run(seed())
    print(f"Добавлено задач: {count} (всего в файле: {len(TASKS)})")
