"""
Проверка окружения: порты БД/Redis принадлежат нашему проекту (S11-007).

Зачем: если порт занят чужим контейнером, приложение подключается к чужой БД
и падает с `password authentication failed` — симптом, который легко принять
за ошибку пароля (KI-001).

Запуск:
    cd backend
    .\\venv\\Scripts\\python.exe scripts/check_ports.py
    .\\venv\\Scripts\\python.exe scripts/check_ports.py --docker

Код возврата: 0 — всё в порядке, 1 — есть проблемы.
"""

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"


async def check_postgres() -> tuple[str, str]:
    """Проверить подключение и «своя ли» база"""
    engine = create_async_engine(settings.database_url, poolclass=None)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            tables = {row[0] for row in result.fetchall()}
    except Exception as exc:  # noqa: BLE001 — диагностика
        return FAIL, f"PostgreSQL {settings.postgres_host}:{settings.postgres_port} — {exc}"
    finally:
        await engine.dispose()

    if not tables:
        return OK, (
            f"PostgreSQL {settings.postgres_host}:{settings.postgres_port} доступен, "
            "база пуста (миграции ещё не применены)"
        )

    expected = {"users", "chat_sessions", "chat_messages", "tasks", "alembic_version"}
    if "alembic_version" not in tables and not tables & expected:
        return WARN, (
            f"PostgreSQL доступен, но таблицы не похожи на наши: {sorted(tables)[:5]}. "
            "Возможно, порт занят чужим контейнером (см. KI-001)"
        )
    if "alembic_version" not in tables:
        return WARN, (
            "База содержит наши таблицы, но нет alembic_version — "
            "миграции применялись вручную?"
        )
    return OK, (
        f"PostgreSQL {settings.postgres_host}:{settings.postgres_port}, "
        f"таблиц: {len(tables)}"
    )


async def check_redis() -> tuple[str, str]:
    """Проверить Redis"""
    from app.db.redis import close_redis, get_redis

    try:
        pong = await get_redis().ping()
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"Redis {settings.redis_host}:{settings.redis_port} — {exc}"
    finally:
        await close_redis()

    if pong:
        return OK, f"Redis {settings.redis_host}:{settings.redis_port} отвечает PONG"
    return FAIL, f"Redis {settings.redis_host}:{settings.redis_port} не отвечает"


def check_docker_ports() -> tuple[str, str]:
    """Опционально: проверить, что порты опубликованы нашими контейнерами"""
    if shutil.which("docker") is None:
        return WARN, "docker не найден в PATH — проверка контейнеров пропущена"

    try:
        output = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return WARN, f"не удалось выполнить docker ps: {exc}"

    postgres_ok = any(
        "ai_teacher_postgres" in line and f":{settings.postgres_port}->" in line
        for line in output.splitlines()
    )
    redis_ok = any(
        "ai_teacher_redis" in line and f":{settings.redis_port}->" in line
        for line in output.splitlines()
    )

    if postgres_ok and redis_ok:
        return OK, "контейнеры публикуют ожидаемые порты"
    missing = []
    if not postgres_ok:
        missing.append(f"postgres:{settings.postgres_port}")
    if not redis_ok:
        missing.append(f"redis:{settings.redis_port}")
    return WARN, (
        "не найдено публикации портов: "
        + ", ".join(missing)
        + ". Порт мог занять другой контейнер (KI-001)"
    )


async def main(with_docker: bool) -> int:
    checks: list[tuple[str, str, str]] = []

    for name, checker in (("postgres", check_postgres), ("redis", check_redis)):
        status, message = await checker()
        checks.append((name, status, message))

    if with_docker:
        status, message = check_docker_ports()
        checks.append(("docker", status, message))

    failed = False
    print("Проверка окружения AI Teacher\n")
    for name, status, message in checks:
        print(f"[{status:4}] {name:9} {message}")
        if status == FAIL:
            failed = True

    print()
    if failed:
        print("Есть проблемы: проверьте занятость портов и .env (docs/KNOWN_ISSUES.md, KI-001).")
        return 1
    print("Окружение готово к работе.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверка портов и доступности сервисов")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="дополнительно проверить, что порты принадлежат нашим контейнерам",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.docker)))
