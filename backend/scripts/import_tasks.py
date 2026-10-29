"""
Импорт задач из JSON/YAML-файла (S14-001).

Запуск из `backend/`:

    python scripts/import_tasks.py tasks.yaml
    python scripts/import_tasks.py tasks.json

Формат: массив задач или `{"tasks": [...]}` (см. docs/USER_GUIDE.md).
Дубликаты по заголовку пропускаются; ошибки валидации печатаются в отчёте.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import async_session_factory  # noqa: E402
from app.services.task_import import (  # noqa: E402
    TaskImportFormatError,
    import_tasks,
    parse_task_payload,
)


async def run(path: Path) -> int:
    try:
        items = parse_task_payload(path.read_text(encoding="utf-8"))
    except (OSError, TaskImportFormatError) as exc:
        print(f"Ошибка чтения файла: {exc}")
        return 2

    async with async_session_factory() as session:
        report = await import_tasks(session, items)

    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    return 1 if report.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Импорт учебных задач")
    parser.add_argument("file", type=Path, help="JSON или YAML с задачами")
    args = parser.parse_args()
    return asyncio.run(run(args.file))


if __name__ == "__main__":
    raise SystemExit(main())
