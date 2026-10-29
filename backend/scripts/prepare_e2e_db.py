"""
Подготовка БД для e2e-прогона (S11-001).

Создаёт базу `E2E_DB_NAME` (по умолчанию `ai_teacher_e2e`), если её нет.
Миграции и seed применяет Playwright webServer после этого скрипта.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.config import settings  # noqa: E402


def main() -> int:
    database = os.environ.get("E2E_DB_NAME", "ai_teacher_e2e")
    connection = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute(f'CREATE DATABASE "{database}"')
                print(f"Создана БД {database}")
            else:
                print(f"БД {database} уже существует")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
