#!/usr/bin/env bash
# Бэкап PostgreSQL для AI Teacher for Python (S20-004, расширен S36-006).
#
# Что делает:
#   1. находит контейнер Postgres через `docker compose ps` (не хардкодит имя);
#   2. pg_dump -Fc, проверяет читаемость `pg_restore -l`;
#   3. gzip + опционально age-шифрование (AGE_RECIPIENT);
#   4. пишет sha256;
#   5. опционально выгружает в S3 (AWS_ACCESS_KEY_ID + S3_BUCKET, aws-cli/s3cmd);
#   6. чистит локальные бэкапы по retention;
#   7. пишет `backup_last_success_timestamp` для node-exporter (TEXTFILE_DIR).
#
# Запуск (из корня репозитория или systemd):
#   bash scripts/backup.sh
#   COMPOSE_FILE=docker-compose.yml ENV_FILE=.env bash scripts/backup.sh
#   AGE_RECIPIENT=age1... bash scripts/backup.sh
#
# Код возврата: 0 — успех; 1 — ошибка; 2 — неверные аргументы.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"

# shellcheck source=lib/env.sh
. "${SCRIPT_DIR}/lib/env.sh"
load_env_file "${ENV_FILE}"

CONTAINER="${POSTGRES_CONTAINER:-}"
DB="${POSTGRES_DB:-ai_teacher}"
DB_USER="${POSTGRES_USER:-ai_teacher}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
AGE_RECIPIENT="${AGE_RECIPIENT:-}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-ai-infra-backups/ai-teacher/}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-}"
TEXTFILE_DIR="${TEXTFILE_DIR:-}"
DRY_RUN=0
NO_S3=0

usage() {
    cat <<'EOF'
Бэкап PostgreSQL (pg_dump -Fc → gzip [→ age] → [S3]).

Использование: bash scripts/backup.sh [опции]

  -c CONTAINER  имя контейнера Postgres (по умолчанию — через compose ps)
  -d DB         имя базы данных (default: ai_teacher)
  -u USER       пользователь Postgres (default: ai_teacher)
  -o DIR        каталог для бэкапов (default: <repo>/backups)
  -r DAYS       хранить N дней, 0 — не чистить (default: 14)
  --no-s3       не выгружать в S3 даже при заданных ключах
  --dry-run     показать план, ничего не делать
  -h            эта справка

ENV: COMPOSE_FILE, ENV_FILE, POSTGRES_CONTAINER, AGE_RECIPIENT,
     AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/S3_BUCKET/S3_PREFIX/S3_ENDPOINT_URL,
     TEXTFILE_DIR (node-exporter textfile collector).
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -c) CONTAINER="${2:-}"; shift 2 ;;
        -d) DB="${2:-}"; shift 2 ;;
        -u) DB_USER="${2:-}"; shift 2 ;;
        -o) BACKUP_DIR="${2:-}"; shift 2 ;;
        -r) RETENTION_DAYS="${2:-}"; shift 2 ;;
        --no-s3) NO_S3=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

log() { printf '[backup] %s\n' "$*"; }
fail() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker не найден в PATH"
[[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || fail "-r ожидает целое число дней"

compose_args=(-f "${COMPOSE_FILE}")
if [ -f "${ENV_FILE}" ]; then
    compose_args=(--env-file "${ENV_FILE}" "${compose_args[@]}")
fi

detect_container() {
    if [ -n "${CONTAINER}" ]; then
        printf '%s' "${CONTAINER}"
        return 0
    fi

    local cid
    cid="$(docker compose "${compose_args[@]}" ps -q postgres 2>/dev/null | head -n1 || true)"
    if [ -n "${cid}" ]; then
        printf '%s' "${cid}"
        return 0
    fi
    return 1
}

if ! CONTAINER="$(detect_container)"; then
    fail "не удалось найти контейнер postgres через compose (${COMPOSE_FILE}); задайте -c"
fi

RUNNING="$(docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null || true)"
[ "${RUNNING}" = "true" ] || fail "контейнер ${CONTAINER} не запущен"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SUFFIX=".dump.gz"
if [ -n "${AGE_RECIPIENT}" ]; then
    SUFFIX=".dump.gz.age"
fi
FILE="${BACKUP_DIR}/${DB}_${STAMP}${SUFFIX}"

log "БД: ${CONTAINER}:${DB} → ${FILE}"
log "Сжатие: gzip; шифрование: $([ -n "${AGE_RECIPIENT}" ] && echo "age (${AGE_RECIPIENT})" || echo "нет")"

if [ "${DRY_RUN}" -eq 1 ]; then
    log "DRY-RUN: контейнер найден; дамп и выгрузка не выполнялись"
    exit 0
fi

if [ -n "${AGE_RECIPIENT}" ] && ! command -v age >/dev/null 2>&1; then
    fail "AGE_RECIPIENT задан, но age не установлен"
fi

mkdir -p "${BACKUP_DIR}"
PLAIN="${BACKUP_DIR}/.${DB}_${STAMP}.dump.part"
TMP="${FILE}.part"
trap 'rm -f "${PLAIN}" "${TMP}"' EXIT

log "pg_dump -Fc"
if ! docker exec "${CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB}" -Fc \
        --no-owner --no-privileges > "${PLAIN}"; then
    fail "pg_dump завершился неудачно"
fi
[ -s "${PLAIN}" ] || fail "получен пустой дамп"

log "Проверка архива (pg_restore -l)"
if ! docker exec -i "${CONTAINER}" pg_restore -l < "${PLAIN}" >/dev/null; then
    fail "pg_restore не смог прочитать дамп"
fi

if [ -n "${AGE_RECIPIENT}" ]; then
    gzip -c "${PLAIN}" | age -r "${AGE_RECIPIENT}" -o "${TMP}"
else
    gzip -c "${PLAIN}" > "${TMP}"
fi
rm -f "${PLAIN}"
mv "${TMP}" "${FILE}"
trap - EXIT

# Контрольная сумма
if command -v sha256sum >/dev/null 2>&1; then
    ( cd "${BACKUP_DIR}" && sha256sum "$(basename "${FILE}")" > "$(basename "${FILE}").sha256" )
elif command -v shasum >/dev/null 2>&1; then
    ( cd "${BACKUP_DIR}" && shasum -a 256 "$(basename "${FILE}")" > "$(basename "${FILE}").sha256" )
else
    log "WARN: sha256sum/shasum не найдены — checksum пропущен"
fi
CHECKSUM_FILE="${FILE}.sha256"

# S3 (S36-006): aws-cli или s3cmd, если заданы ключи/бакет.
upload_s3() {
    [ "${NO_S3}" -eq 1 ] && { log "S3: пропущено (--no-s3)"; return 0; }
    if [ -z "${S3_BUCKET}" ] || [ -z "${AWS_ACCESS_KEY_ID:-}" ]; then
        log "S3: ключи/бакет не заданы — бэкап остаётся локально"
        return 0
    fi

    local dest="s3://${S3_BUCKET}/${S3_PREFIX%/}/$(basename "${FILE}")"
    if command -v aws >/dev/null 2>&1; then
        local endpoint=()
        [ -n "${S3_ENDPOINT_URL}" ] && endpoint=(--endpoint-url "${S3_ENDPOINT_URL}")
        aws "${endpoint[@]}" s3 cp "${FILE}" "${dest}" --only-show-errors
        [ -f "${CHECKSUM_FILE}" ] && aws "${endpoint[@]}" s3 cp "${CHECKSUM_FILE}" "${dest}.sha256" --only-show-errors
        log "S3: загружено ${dest}"
    elif command -v s3cmd >/dev/null 2>&1; then
        s3cmd put "${FILE}" "${dest}"
        [ -f "${CHECKSUM_FILE}" ] && s3cmd put "${CHECKSUM_FILE}" "${dest}.sha256"
        log "S3: загружено ${dest} (s3cmd)"
    else
        log "S3: aws-cli/s3cmd не найдены — бэкап остаётся локально"
    fi
}
upload_s3 || log "WARN: выгрузка в S3 не удалась (локальный бэкап сохранён)"

# Retention локально
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    while IFS= read -r OLD; do
        [ -n "${OLD}" ] || continue
        rm -f "${OLD}" "${OLD}.sha256"
        log "Удалён старый бэкап: ${OLD}"
    done < <(find "${BACKUP_DIR}" -maxdepth 1 -type f \( -name "${DB}_*.dump.gz" -o -name "${DB}_*.dump.gz.age" \) \
                -mtime +"${RETENTION_DAYS}" | sort)
fi

# Метрика для алерта BackupStale (S35-003/S36-006)
if [ -n "${TEXTFILE_DIR}" ]; then
    if [ -d "${TEXTFILE_DIR}" ] && [ -w "${TEXTFILE_DIR}" ]; then
        METRIC="${TEXTFILE_DIR}/ai_teacher_backup.prom"
        SIZE_BYTES="$(wc -c < "${FILE}" | tr -d ' ')"
        {
            echo "# HELP backup_last_success_timestamp Unix timestamp последнего успешного бэкапа"
            echo "# TYPE backup_last_success_timestamp gauge"
            echo "backup_last_success_timestamp $(date -u +%s)"
            echo "# HELP backup_size_bytes Размер последнего бэкапа"
            echo "# TYPE backup_size_bytes gauge"
            echo "backup_size_bytes ${SIZE_BYTES}"
        } > "${METRIC}.tmp"
        mv "${METRIC}.tmp" "${METRIC}"
        log "Метрика: ${METRIC}"
    else
        log "WARN: TEXTFILE_DIR ${TEXTFILE_DIR} недоступен для записи"
    fi
fi

SIZE="$(du -h "${FILE}" | cut -f1)"
log "OK: ${FILE} (${SIZE}); retention ${RETENTION_DAYS} дн."
log "Восстановление: bash scripts/restore.sh -f \"${FILE}\" -t <db> --create -y --verify"
