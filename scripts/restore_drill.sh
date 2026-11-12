#!/usr/bin/env bash
# Тестовое восстановление последнего бэкапа в scratch-БД (S36-007).
#
# Не трогает рабочую БД: создаёт `ai_teacher_drill_<UTC>`, восстанавливает
# дамп через scripts/restore.sh, проверяет схему/данные и удаляет scratch.
# Лог пишется в ${BACKUP_DIR}/dr-reports/ (gitignored).
#
# Использование:
#   bash scripts/restore_drill.sh                 # последний бэкап
#   bash scripts/restore_drill.sh -f backups/...  # конкретный файл
#   bash scripts/restore_drill.sh --keep          # оставить scratch-БД
#   bash scripts/restore_drill.sh --dry-run
#
# Код возврата: 0 — успех; 1 — ошибка; 2 — аргументы.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"

# shellcheck source=lib/env.sh
. "${SCRIPT_DIR}/lib/env.sh"
load_env_file "${ENV_FILE}"

BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
CONTAINER="${POSTGRES_CONTAINER:-}"
DB_USER="${POSTGRES_USER:-ai_teacher}"
SOURCE_DB="${POSTGRES_DB:-ai_teacher}"
BACKUP_FILE=""
KEEP=0
DRY_RUN=0

usage() {
    cat <<'EOF'
Restore drill: восстановление бэкапа в scratch-БД и проверки.

Использование: bash scripts/restore_drill.sh [опции]

  -f FILE       файл бэкапа (default: последний в BACKUP_DIR)
  -c CONTAINER  контейнер Postgres (default: через compose ps)
  -u USER       пользователь Postgres (default: POSTGRES_USER)
  --keep        не удалять scratch-БД
  --dry-run     показать план
  -h            эта справка
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -f) BACKUP_FILE="${2:-}"; shift 2 ;;
        -c) CONTAINER="${2:-}"; shift 2 ;;
        -u) DB_USER="${2:-}"; shift 2 ;;
        --keep) KEEP=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

log() { printf '[drill] %s\n' "$*"; }
fail() { printf '[drill] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker не найден"
[ -f "${COMPOSE_FILE}" ] || fail "compose-файл ${COMPOSE_FILE} не найден"

if [ -z "${BACKUP_FILE}" ]; then
    BACKUP_FILE="$(ls -1t "${BACKUP_DIR}"/${SOURCE_DB}_*.dump.gz \
        "${BACKUP_DIR}"/${SOURCE_DB}_*.dump.gz.age 2>/dev/null | head -n1 || true)"
    [ -n "${BACKUP_FILE}" ] || fail "в ${BACKUP_DIR} нет бэкапов ${SOURCE_DB}_*"
fi
[ -f "${BACKUP_FILE}" ] || fail "файл ${BACKUP_FILE} не найден"

compose_args=(-f "${COMPOSE_FILE}")
[ -f "${ENV_FILE}" ] && compose_args=(--env-file "${ENV_FILE}" "${compose_args[@]}")

if [ -z "${CONTAINER}" ]; then
    CONTAINER="$(docker compose "${compose_args[@]}" ps -q postgres 2>/dev/null | head -n1 || true)"
fi
[ -n "${CONTAINER}" ] || fail "не удалось определить контейнер postgres"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET_DB="ai_teacher_drill_${STAMP//[^0-9TZ]/_}"
REPORT_DIR="${BACKUP_DIR}/dr-reports"
mkdir -p "${REPORT_DIR}"
LOG_FILE="${REPORT_DIR}/drill_${STAMP}.log"

log "Бэкап: ${BACKUP_FILE}"
log "Scratch-БД: ${TARGET_DB}"
log "Отчёт: ${LOG_FILE}"

if [ "${DRY_RUN}" -eq 1 ]; then
    log "DRY-RUN: restore.sh -f ${BACKUP_FILE} -t ${TARGET_DB} --create -y --verify"
    exit 0
fi

# Дублируем вывод в лог.
exec > >(tee -a "${LOG_FILE}") 2>&1

cleanup() {
    if [ "${KEEP}" -eq 0 ]; then
        docker exec "${CONTAINER}" psql -U "${DB_USER}" -d postgres -c \
            "DROP DATABASE IF EXISTS \"${TARGET_DB}\" WITH (FORCE)" >/dev/null 2>&1 || true
        log "Scratch-БД ${TARGET_DB} удалена"
    else
        log "Scratch-БД ${TARGET_DB} оставлена (--keep)"
    fi
}
trap cleanup EXIT

log "Восстановление..."
args=(-f "${BACKUP_FILE}" -t "${TARGET_DB}" -c "${CONTAINER}" -u "${DB_USER}" \
      --create -y --verify)
if [ -n "${AGE_IDENTITY:-}" ]; then
    args+=(--age-identity "${AGE_IDENTITY}")
fi
bash "${SCRIPT_DIR}/restore.sh" "${args[@]}"

log "Проверки после восстановления"
TABLE_COUNT="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" \
    | tr -d '[:space:]')"
[ "${TABLE_COUNT}" -gt 0 ] || fail "в scratch-БД нет таблиц"

ALEMBIC="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM alembic_version" | tr -d '[:space:]')"
[ "${ALEMBIC}" = "1" ] || fail "alembic_version пуст/отсутствует"

USERS="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM users" | tr -d '[:space:]')"

log "Таблиц: ${TABLE_COUNT}; users: ${USERS}; alembic_version: OK"
log "OK: restore drill успешен"
