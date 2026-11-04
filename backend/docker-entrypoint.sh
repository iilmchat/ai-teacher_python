#!/bin/sh
# Точка входа backend-контейнера (S20-006).
#
# На чистой БД API не может работать, пока не применены миграции: без этого
# первый же запрос падает с UndefinedTableError. Поэтому при старте контейнера
# выполняем `alembic upgrade head` (идемпотентно), затем запускаем CMD.
#
# Отключить авто-миграции (например, при выкатке миграций отдельным job'ом):
#   SKIP_MIGRATIONS=true
set -e

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    echo "docker-entrypoint: applying database migrations (alembic upgrade head)"
    alembic upgrade head
else
    echo "docker-entrypoint: SKIP_MIGRATIONS=true — migrations are not applied"
fi

# KI-024: в multiprocess-режиме Prometheus каталог должен быть пустым на старте —
# файлы прошлого запуска исказили бы счётчики. Чистка только здесь: внутри
# воркеров удаление стёрло бы значения уже работающих реплик.
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
    rm -f "$PROMETHEUS_MULTIPROC_DIR"/*.db
    echo "docker-entrypoint: multiprocess metrics dir cleaned ($PROMETHEUS_MULTIPROC_DIR)"
fi

exec "$@"
