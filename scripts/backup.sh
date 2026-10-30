#!/usr/bin/env bash
# Бэкап PostgreSQL для AI Teacher for Python (S20-004).
#
# Делает логический дамп рабочей БД через `docker exec <container> pg_dump`
# в custom-format (-Fc), сжимает gzip, пишет контрольную сумму и чистит
# старые бэкапы по retention. Восстановление — scripts/restore.sh.
#
# Запуск (из корня репозитория, Git Bash / Linux / macOS):
#   bash scripts/backup.sh
#   bash scripts/backup.sh -o /backups -r 30
#   bash scripts/backup.sh -c ai_teacher_postgres -d ai_teacher -u ai_teacher
#
# Параметры можно задать и через ENV:
#   POSTGRES_CONTAINER, POSTGRES_DB, POSTGRES_USER, BACKUP_DIR,
#   BACKUP_RETENTION_DAYS
#
# Код возврата: 0 — успех; 1 — ошибка; 2 — неверные аргументы.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONTAINER="${POSTGRES_CONTAINER:-ai_teacher_postgres}"
DB="${POSTGRES_DB:-ai_teacher}"
DB_USER="${POSTGRES_USER:-ai_teacher}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

usage() {
    cat <<'EOF'
Бэкап PostgreSQL (pg_dump -Fc | gzip) через docker exec.

Использование: bash scripts/backup.sh [опции]

  -c CONTAINER  имя контейнера Postgres (default: ai_teacher_postgres)
  -d DB         имя базы данных (default: ai_teacher)
  -u USER       пользователь Postgres (default: ai_teacher)
  -o DIR        каталог для бэкапов (default: <repo>/backups)
  -r DAYS       хранить бэкапы N дней, 0 — не чистить (default: 14)
  -h            эта справка

Формат файла: <DB>_<UTC timestamp>.dump.gz (+ .sha256).
EOF
}

while getopts ":c:d:u:o:r:h" opt; do
    case "${opt}" in
        c) CONTAINER="${OPTARG}" ;;
        d) DB="${OPTARG}" ;;
        u) DB_USER="${OPTARG}" ;;
        o) BACKUP_DIR="${OPTARG}" ;;
        r) RETENTION_DAYS="${OPTARG}" ;;
        h) usage; exit 0 ;;
        :) echo "Ошибка: -${OPTARG} требует аргумент" >&2; usage; exit 2 ;;
        \?) echo "Ошибка: неизвестный флаг -${OPTARG}" >&2; usage; exit 2 ;;
    esac
done

if ! command -v docker >/dev/null 2>&1; then
    echo "Ошибка: docker не найден в PATH" >&2
    exit 1
fi

if ! [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]]; then
    echo "Ошибка: -r ожидает целое число дней, получено: ${RETENTION_DAYS}" >&2
    exit 2
fi

# 1. Контейнер должен быть запущен (иначе pg_dump уйдёт в чужую БД — KI-001)
RUNNING="$(docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null || true)"
if [ "${RUNNING}" != "true" ]; then
    echo "Ошибка: контейнер ${CONTAINER} не запущен (docker ps)" >&2
    exit 1
fi

# 2. Подготовка каталога
mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="${BACKUP_DIR}/${DB}_${STAMP}.dump.gz"
TMP="${FILE}.part"

echo "Бэкап: ${CONTAINER}:${DB}  ->  ${FILE}"

# 3. Дамп: pg_dump пишет в stdout, gzip — в файл
if ! docker exec "${CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB}" -Fc \
        --no-owner --no-privileges | gzip -c > "${TMP}"; then
    echo "Ошибка: pg_dump завершился неудачно" >&2
    rm -f "${TMP}"
    exit 1
fi

if [ ! -s "${TMP}" ]; then
    echo "Ошибка: получен пустой дамп" >&2
    rm -f "${TMP}"
    exit 1
fi

if ! gzip -t "${TMP}" 2>/dev/null; then
    echo "Ошибка: архив gzip повреждён" >&2
    rm -f "${TMP}"
    exit 1
fi

# 4. Проверка читаемости архива pg_restore (без восстановления)
if gzip -dc "${TMP}" | docker exec -i "${CONTAINER}" pg_restore -l > /dev/null; then
    echo "Проверка архива: pg_restore -l OK"
else
    echo "Ошибка: pg_restore не смог прочитать дамп" >&2
    rm -f "${TMP}"
    exit 1
fi

mv "${TMP}" "${FILE}"

# 5. Контрольная сумма
if command -v sha256sum >/dev/null 2>&1; then
    ( cd "${BACKUP_DIR}" && sha256sum "$(basename "${FILE}")" > "$(basename "${FILE}").sha256" )
    echo "Контрольная сумма: $(basename "${FILE}").sha256"
elif command -v shasum >/dev/null 2>&1; then
    ( cd "${BACKUP_DIR}" && shasum -a 256 "$(basename "${FILE}")" > "$(basename "${FILE}").sha256" )
    echo "Контрольная сумма: $(basename "${FILE}").sha256"
else
    echo "Предупреждение: sha256sum/shasum не найдены — checksum пропущен" >&2
fi

# 6. Retention: удаляем только дампы этой БД старше N дней (+ их checksum)
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    while IFS= read -r OLD; do
        [ -n "${OLD}" ] || continue
        rm -f "${OLD}" "${OLD}.sha256"
        echo "Удалён старый бэкап: ${OLD}"
    done < <(find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${DB}_*.dump.gz" \
                -mtime +"${RETENTION_DAYS}" | sort)
fi

SIZE="$(du -h "${FILE}" | cut -f1)"
echo "OK: ${FILE} (${SIZE}); retention ${RETENTION_DAYS} дн."
echo "Восстановление: bash scripts/restore.sh -f \"${FILE}\" -t <target_db> --create"
