"""
Тесты миграций Alembic (S11-005, закрывает KI-002).

Проверяют, что миграции применяются на пустую БД, откатываются и применяются
снова, а схема после upgrade соответствует моделям.

Работают на отдельной БД `ai_teacher_migrations`, чтобы не мешать остальным
тестам. Запускаются маркером `migrations` (см. pyproject.toml).
"""

from pathlib import Path

import psycopg2
import pytest
from alembic import command
from alembic.config import Config

import app.models  # noqa: F401  — регистрирует модели в Base.metadata
from app.config import settings
from app.db.database import Base

pytestmark = pytest.mark.migrations

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DB = "ai_teacher_migrations"


def _connect_admin():
    connection = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
    )
    connection.autocommit = True
    return connection


def _connect_test_db():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=MIGRATIONS_DB,
    )


def _table_names(connection) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        return {row[0] for row in cursor.fetchall()}


def _all_columns(connection) -> dict[str, set[str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
        columns: dict[str, set[str]] = {}
        for table, column in cursor.fetchall():
            columns.setdefault(table, set()).add(column)
        return columns


@pytest.fixture
def migrations_database(monkeypatch: pytest.MonkeyPatch):
    """Чистая БД для прогона миграций"""
    admin = _connect_admin()
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{MIGRATIONS_DB}" WITH (FORCE)')
            cursor.execute(f'CREATE DATABASE "{MIGRATIONS_DB}"')
    finally:
        admin.close()

    original_db = settings.postgres_db
    monkeypatch.setattr(settings, "postgres_db", MIGRATIONS_DB)
    try:
        yield
    finally:
        monkeypatch.setattr(settings, "postgres_db", original_db)
        admin = _connect_admin()
        try:
            with admin.cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS "{MIGRATIONS_DB}" WITH (FORCE)')
        finally:
            admin.close()


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def test_upgrade_creates_all_tables(migrations_database) -> None:
    """Upgrade head создаёт все таблицы моделей"""
    command.upgrade(_alembic_config(), "head")

    connection = _connect_test_db()
    try:
        tables = _table_names(connection)
    finally:
        connection.close()

    expected = set(Base.metadata.tables.keys()) | {"alembic_version"}
    assert expected <= tables, f"не созданы таблицы: {expected - tables}"


def test_upgraded_schema_matches_models(migrations_database) -> None:
    """Колонки из моделей присутствуют в БД после upgrade"""
    command.upgrade(_alembic_config(), "head")

    connection = _connect_test_db()
    try:
        columns = _all_columns(connection)
    finally:
        connection.close()

    missing: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        db_columns = columns.get(table_name, set())
        for column in table.columns:
            if column.name not in db_columns:
                missing.append(f"{table_name}.{column.name}")

    assert not missing, f"в БД отсутствуют колонки: {missing}"


def test_downgrade_and_upgrade_again(migrations_database) -> None:
    """downgrade base → upgrade head работает повторно (идемпотентность)"""
    config = _alembic_config()

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    connection = _connect_test_db()
    try:
        tables_after_downgrade = _table_names(connection)
    finally:
        connection.close()

    # После полного отката остаётся только служебная таблица версий
    assert tables_after_downgrade <= {"alembic_version"}

    command.upgrade(config, "head")

    connection = _connect_test_db()
    try:
        tables_after_second_upgrade = _table_names(connection)
    finally:
        connection.close()

    expected = set(Base.metadata.tables.keys())
    assert expected <= tables_after_second_upgrade


def test_head_is_single(migrations_database) -> None:
    """В цепочке ровно одна голова (нет ветвления миграций)"""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()

    assert len(heads) == 1, f"несколько голов: {heads}"
