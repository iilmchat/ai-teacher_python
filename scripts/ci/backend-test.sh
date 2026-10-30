#!/usr/bin/env bash
# CI: backend tests (pytest на реальном PostgreSQL/pgvector + Redis).
# Ожидает сервисные контейнеры в одной docker-сети с именами (alias)
# `postgres` и `redis`; переменные POSTGRES_*/REDIS_* задаёт вызывающий
# (workflow/GitFlic job). Здесь — только ожидание готовности и прогон.
set -euo pipefail

# См. backend-lint.sh: нестабильный PyPI (KI-017) — таймауты, ретраи, кэш pip.
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-60}"
export PIP_RETRIES="${PIP_RETRIES:-5}"

WORKSPACE=/workspace
mkdir -p "$WORKSPACE"
cd /src
tar --exclude=backend/venv \
    --exclude=backend/.mypy_cache \
    --exclude=backend/.pytest_cache \
    --exclude=backend/.ruff_cache \
    --exclude=backend/.coverage \
    -cf - backend pyproject.toml | tar -xf - -C "$WORKSPACE"
cd "$WORKSPACE"

# Адреса сервисов фиксируем явно: переменная проекта с тем же именем иначе
# перекрыла бы значения (см. docs/CI.md §4).
export POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export REDIS_HOST="${REDIS_HOST:-redis}"
export REDIS_PORT="${REDIS_PORT:-6379}"

echo "==> установка зависимостей backend (pip cache: ${PIP_CACHE_DIR:-/workspace/.pip-cache})"
python -m pip install --upgrade pip >/dev/null
pip install -r backend/requirements.txt >/dev/null

echo "==> ожидание PostgreSQL (до 60 с)"
python - <<'PY'
import os
import socket
import sys
import time

import psycopg2

host = os.environ["POSTGRES_HOST"]
port = int(os.environ["POSTGRES_PORT"])


def tcp_open() -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    if tcp_open():
        break
    time.sleep(2)
else:
    sys.exit(f"PostgreSQL {host}:{port} не открылся за 60 с")

try:
    psycopg2.connect(
        host=host,
        port=port,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    ).close()
except Exception as exc:  # noqa: BLE001 — нужен понятный текст ошибки
    sys.exit(f"PostgreSQL открыт, но вход не удался ({host}:{port}): {exc}")
print(f"PostgreSQL готов: {host}:{port}")
PY

echo "==> ожидание Redis (до 60 с)"
python - <<'PY'
import os
import sys
import time

import redis

host = os.environ["REDIS_HOST"]
port = int(os.environ["REDIS_PORT"])
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        if redis.Redis(host=host, port=port, socket_connect_timeout=2).ping():
            break
    except Exception:  # noqa: BLE001 — сервис ещё поднимается
        time.sleep(2)
else:
    sys.exit(f"Redis {host}:{port} недоступен за 60 с")
print(f"Redis готов: {host}:{port}")
PY

cd "$WORKSPACE/backend"
echo "==> alembic upgrade head"
alembic upgrade head
echo "==> alembic check (модели == миграции, RULES §11.5)"
alembic check
echo "==> pytest"
pytest -q
echo "==> BACKEND TEST OK"
