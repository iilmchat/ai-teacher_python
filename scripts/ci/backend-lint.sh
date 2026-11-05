#!/usr/bin/env bash
# CI: backend lint (ruff + mypy) — запускается в python:3.12-slim с репозиторием
# в /src (read-only). Копируем нужное в /workspace, чтобы кэши mypy/ruff
# не писали в смонтированный read-only репозиторий.
set -euo pipefail

# PyPI с self-hosted runner'а нестабилен (KI-017): TLS-хендшейк иногда
# «залипает». Увеличиваем таймаут/ретраи; кэш pip переиспользуется между
# прогонами (named volume `ai-teacher-pip-cache` в workflow), иначе каждый job
# качает одни и те же колёса заново.
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-60}"
export PIP_RETRIES="${PIP_RETRIES:-5}"

# S33-001: тег образа — изменяемая ссылка; сборка воспроизводима только с
# digest. Проверяем Dockerfile'ы и compose до сборки (stdlib, без зависимостей).
echo "==> python backend/scripts/check_image_pins.py --root /src"
python /src/backend/scripts/check_image_pins.py --root /src

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
# wheelhouse -> PyPI (см. install-python-deps.sh): на self-hosted runner'е PyPI
# нестабилен (KI-017), колеса приходят из named volume /wheelhouse.
bash /src/scripts/ci/install-python-deps.sh "$WORKSPACE/backend/requirements.txt"
# ruff/mypy закреплены в requirements.txt (dev) — версии обновляются там же

cd "$WORKSPACE/backend"
echo "==> ruff check app tests scripts"
ruff check app tests scripts
echo "==> mypy app --config-file ../pyproject.toml"
mypy app --config-file ../pyproject.toml
echo "==> BACKEND LINT OK"
