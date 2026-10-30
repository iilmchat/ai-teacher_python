#!/usr/bin/env bash
# CI: backend lint (ruff + mypy) — запускается в python:3.12-slim с репозиторием
# в /src (read-only). Копируем нужное в /workspace, чтобы кэши mypy/ruff
# не писали в смонтированный read-only репозиторий.
set -euo pipefail

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

echo "==> установка зависимостей (mypy нужны импортируемые пакеты, иначе"
echo "    'Cannot find implementation ... fastapi/sqlalchemy' — найдено на self-hosted run)"
python -m pip install --upgrade pip >/dev/null
pip install -r "$WORKSPACE/backend/requirements.txt" >/dev/null
# ruff/mypy уже закреплены в requirements.txt (dev): ruff==0.8.1, mypy==1.13.0

cd "$WORKSPACE/backend"
echo "==> ruff check app tests scripts"
ruff check app tests scripts
echo "==> mypy app --config-file ../pyproject.toml"
mypy app --config-file ../pyproject.toml
echo "==> BACKEND LINT OK"
