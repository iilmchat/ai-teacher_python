"""
Pytest configuration and fixtures.

Тесты работают на реальном PostgreSQL с pgvector: SQLite не поддерживает
JSONB и тип VECTOR. Каждый тест выполняется в транзакции, которая
откатывается в конце — состояние между тестами не разделяется (RULES §4.4).

Создание тестовой БД выполняется синхронно (psycopg2) в session-scoped
фикстуре: это исключает привязку async-фикстур к чужому event loop.
"""
from collections.abc import AsyncGenerator, Iterator

import psycopg2
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  # регистрирует все модели в Base.metadata
from app.config import settings
from app.data.achievements import ACHIEVEMENTS
from app.db.database import Base, get_db
from app.main import app
from app.models.engagement import Achievement

TEST_DB_NAME = "ai_teacher_test"


def _database_url(database: str) -> str:
    """Async URL подключения к указанной БД на тестовом сервере"""
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{database}"
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database() -> Iterator[None]:
    """Пересоздаёт чистую тестовую БД перед запуском тестов"""
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
            cursor.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            cursor.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        connection.close()
    yield


@pytest.fixture(autouse=True)
def disable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """По умолчанию лимиты выключены, чтобы не влиять на другие тесты.

    Тесты лимитов включают флаг сами (см. `test_rate_limit.py`).
    """
    monkeypatch.setattr(settings, "rate_limit_enabled", False)


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """По умолчанию Redis-кэш выключен: тесты не ходят во внешний Redis.

    Тесты кэша включают флаг сами и подставляют in-memory FakeRedis
    (`set_redis_client`). Состояние метрик и «остывание» сбрасываются
    между тестами, иначе счётчики протекают.
    """
    from app.db.redis import set_redis_client
    from app.services.cache import reset_cache_state

    monkeypatch.setattr(settings, "cache_enabled", False)
    set_redis_client(None)
    reset_cache_state()
    yield
    set_redis_client(None)
    reset_cache_state()


@pytest_asyncio.fixture
async def test_engine():
    """Engine к тестовой БД; схема создаётся при необходимости"""
    engine = create_async_engine(_database_url(TEST_DB_NAME), poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # create_all не выполняет seed из миграции 008 — добавляем справочник
        await conn.execute(
            pg_insert(Achievement)
            .values(ACHIEVEMENTS)
            .on_conflict_do_nothing(index_elements=["code"])
        )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Сессия БД в транзакции; в конце теста изменения откатываются"""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент с подменой зависимости get_db на тестовую сессию"""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
