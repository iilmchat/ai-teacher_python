#!/usr/bin/env bash
# Восстановление PostgreSQL из бэкапа, созданного scripts/backup.sh (S20-004).
#
# Безопасность:
#   - по умолчанию НЕ восстанавливает в рабочую БД (POSTGRES_DB, обычно
#     ai_teacher): требуется --force;
#   - требует подтверждения (ввести "yes"), если не указан -y;
#   - запрещает восстановление в служебные БД postgres/template0/template1;
#   - --create создаёт целевую БД (для smoke-проверки на scratch-БД).
#
# Запуск:
#   bash scripts/restore.sh -f backups/ai_teacher_20261030T090000Z.dump.gz \
#        -t ai_teacher_restore_check --create -y --verify
#
# Код возврата: 0 — успех; 1 — ошибка; 2 — неверные аргументы/отказ.
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-ai_teacher_postgres}"
DB_USER="${POSTGRES_USER:-ai_teacher}"
SOURCE_DB="${POSTGRES_DB:-ai_teacher}"

BACKUP_FILE=""
TARGET_DB="ai_teacher_restore_check"
ASSUME_YES=0
CREATE_DB=0
CLEAN=0
FORCE=0
VERIFY=0

usage() {
    cat <<'EOF'
Восстановление PostgreSQL из бэкапа backup.sh (pg_restore).

Использование: bash scripts/restore.sh -f FILE [опции]

  -f FILE       файл бэкапа *.dump.gz (обязательно)
  -t DB         целевая БД (default: ai_teacher_restore_check)
  -c CONTAINER  имя контейнера Postgres (default: ai_teacher_postgres)
  -u USER       пользователь Postgres (default: ai_teacher)
  --create      создать целевую БД, если её нет
  --clean       удалить объекты в целевой БД перед восстановлением
  --force       разрешить восстановление поверх рабочей БД (POSTGRES_DB)
  -y            не спрашивать подтверждение
  --verify      напечатать количество таблиц и строк после восстановления
  -h            эта справка

Пример smoke-проверки:
  bash scripts/backup.sh
  bash scripts/restore.sh -f backups/ai_teacher_<stamp>.dump.gz \
       -t ai_teacher_restore_check --create -y --verify
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -f) BACKUP_FILE="${2:-}"; shift 2 ;;
        -t) TARGET_DB="${2:-}"; shift 2 ;;
        -c) CONTAINER="${2:-}"; shift 2 ;;
        -u) DB_USER="${2:-}"; shift 2 ;;
        --create) CREATE_DB=1; shift ;;
        --clean) CLEAN=1; shift ;;
        --force) FORCE=1; shift ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        --verify) VERIFY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

if [ -z "${BACKUP_FILE}" ]; then
    echo "Ошибка: не указан файл бэкапа (-f)" >&2
    usage
    exit 2
fi
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Ошибка: файл не найден: ${BACKUP_FILE}" >&2
    exit 1
fi
if [ -z "${TARGET_DB}" ]; then
    echo "Ошибка: пустое имя целевой БД" >&2
    exit 2
fi

# Служебные БД восстанавливать нельзя
case "${TARGET_DB}" in
    postgres|template0|template1)
        echo "Ошибка: восстановление в служебную БД ${TARGET_DB} запрещено" >&2
        exit 2
        ;;
esac

# Защита рабочей БД: только с --force
if [ "${TARGET_DB}" = "${SOURCE_DB}" ] && [ "${FORCE}" -ne 1 ]; then
    echo "Ошибка: ${TARGET_DB} — рабочая БД. Используйте отдельную БД или --force." >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Ошибка: docker не найден в PATH" >&2
    exit 1
fi
RUNNING="$(docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null || true)"
if [ "${RUNNING}" != "true" ]; then
    echo "Ошибка: контейнер ${CONTAINER} не запущен" >&2
    exit 1
fi

if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
    echo "Ошибка: ${BACKUP_FILE} не является валидным gzip" >&2
    exit 1
fi

# Подтверждение
if [ "${ASSUME_YES}" -ne 1 ]; then
    echo "Будет восстановлена БД '${TARGET_DB}' из '${BACKUP_FILE}'."
    echo "Текущие объекты в '${TARGET_DB}' могут быть перезаписаны (--clean)."
    printf "Введите 'yes' для продолжения: "
    read -r ANSWER
    if [ "${ANSWER}" != "yes" ]; then
        echo "Отменено пользователем" >&2
        exit 2
    fi
fi

# Проверка/создание целевой БД
DB_EXISTS="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}'" | tr -d '[:space:]')"

if [ "${DB_EXISTS}" != "1" ]; then
    if [ "${CREATE_DB}" -ne 1 ]; then
        echo "Ошибка: БД '${TARGET_DB}' не существует (используйте --create)" >&2
        exit 1
    fi
    echo "Создаю БД ${TARGET_DB}..."
    docker exec "${CONTAINER}" createdb -U "${DB_USER}" -T template0 "${TARGET_DB}"
fi

RESTORE_ARGS=(-U "${DB_USER}" -d "${TARGET_DB}" --no-owner --no-privileges)
if [ "${CLEAN}" -eq 1 ]; then
    RESTORE_ARGS+=(--clean --if-exists)
fi

echo "Восстановление ${BACKUP_FILE} -> ${CONTAINER}:${TARGET_DB} ..."
if ! gzip -dc "${BACKUP_FILE}" | docker exec -i "${CONTAINER}" pg_restore "${RESTORE_ARGS[@]}"; then
    echo "Ошибка: pg_restore завершился неудачно" >&2
    exit 1
fi

# Проверка результата
TABLE_COUNT="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'" \
    | tr -d '[:space:]')"
echo "Восстановлено таблиц (public): ${TABLE_COUNT}"

if [ "${VERIFY}" -eq 1 ]; then
    echo "Строки в таблицах:"
    TABLES="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")"
    if [ -z "${TABLES}" ]; then
        echo "  (таблиц нет — проверьте бэкап)" >&2
        exit 1
    fi
    while IFS= read -r TABLE; do
        [ -n "${TABLE}" ] || continue
        ROWS="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
            "SELECT count(*) FROM \"${TABLE}\"" | tr -d '[:space:]')"
        printf '  %-40s %s\n' "${TABLE}" "${ROWS}"
    done <<< "${TABLES}"
fi

if [ "${TARGET_DB}" = "${SOURCE_DB}" ]; then
    echo "OK: восстановление в рабочую БД ${TARGET_DB} завершено (--force)"
else
    echo "OK: восстановление в ${TARGET_DB} завершено."
    echo "Удалить scratch-БД: docker exec ${CONTAINER} dropdb -U ${DB_USER} ${TARGET_DB}"
fi
