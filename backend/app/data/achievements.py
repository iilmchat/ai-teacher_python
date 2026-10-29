"""Справочник достижений (S17-001).

Те же строки вставляет миграция 008; константы нужны тестам и seed-проверкам.
"""

ACHIEVEMENTS: list[dict[str, str]] = [
    {
        "code": "first_task",
        "title": "Первая задача",
        "description": "Решена первая задача",
        "icon": "🚀",
    },
    {
        "code": "ten_tasks",
        "title": "Десятка",
        "description": "Решено десять задач",
        "icon": "🔟",
    },
    {
        "code": "streak_3",
        "title": "Три дня подряд",
        "description": "Занятия три дня подряд",
        "icon": "🔥",
    },
    {
        "code": "all_easy",
        "title": "Лёгкая серия",
        "description": "Решены все лёгкие задачи",
        "icon": "🟢",
    },
    {
        "code": "all_medium",
        "title": "Средняя серия",
        "description": "Решены все средние задачи",
        "icon": "🟡",
    },
    {
        "code": "all_hard",
        "title": "Сложная серия",
        "description": "Решены все сложные задачи",
        "icon": "🔴",
    },
]
