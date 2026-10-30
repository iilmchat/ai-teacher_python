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

exec "$@"
