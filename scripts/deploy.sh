#!/usr/bin/env bash
# Деплой AI Teacher for Python (S36-004/005).
#
# Шаги:
#   1. валидация окружения (.env.prod, секреты, compose config);
#   2. бэкап БД (если не --no-backup);
#   3. миграции отдельным one-shot контейнером `migrate`;
#   4. pull образов по тегу/digest и `up -d --no-deps --remove-orphans`;
#   5. healthcheck /health/ready через backend;
#   6. при провале — автоматический откат на предыдущее состояние (.last_deploy).
#
# Использование:
#   bash scripts/deploy.sh [--dry-run] [--no-backup] [--no-pull] [--skip-migrations]
#   IMAGE_TAG=v0.6.0 bash scripts/deploy.sh
#
# Код возврата: 0 — успех; 1 — ошибка/неудачный healthcheck; 2 — аргументы/конфиг.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
STATE_FILE="${DEPLOY_STATE:-${ROOT_DIR}/.deploy-state}"
LAST_FILE="${DEPLOY_LAST:-${ROOT_DIR}/.last_deploy}"
HEALTH_RETRIES="${DEPLOY_HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${DEPLOY_HEALTH_INTERVAL:-2}"
HEALTH_URL="${DEPLOY_HEALTHCHECK_URL:-}"

DRY_RUN=0
NO_BACKUP=0
NO_PULL=0
SKIP_MIGRATIONS=0

usage() {
    cat <<'EOF'
Деплой prod-стека (GHCR + Caddy).

Использование: bash scripts/deploy.sh [опции]

  --dry-run            проверить конфиг и показать шаги, ничего не менять
  --no-backup          не делать бэкап перед деплоем
  --no-pull            не делать docker compose pull (образы уже локально)
  --skip-migrations    не запускать контейнер migrate
  --env-file FILE      env-файл (default: .env.prod)
  --compose-file FILE  compose-файл (default: docker-compose.prod.yml)
  -h, --help           эта справка

ENV: IMAGE_TAG, BACKEND_IMAGE/FRONTEND_IMAGE/SANDBOX_IMAGE (digest),
     DEPLOY_HEALTHCHECK_URL (если задан — curl вместо docker exec).
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --no-backup) NO_BACKUP=1; shift ;;
        --no-pull) NO_PULL=1; shift ;;
        --skip-migrations) SKIP_MIGRATIONS=1; shift ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --compose-file) COMPOSE_FILE="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker не найден"
[ -f "${ENV_FILE}" ] || fail "${ENV_FILE} не найден (скопируйте .env.prod.example)"
[ -f "${COMPOSE_FILE}" ] || fail "${COMPOSE_FILE} не найден"

# Загружаем ENV в окружение скрипта (нужно backup.sh и healthcheck).
# shellcheck source=lib/env.sh
. "${SCRIPT_DIR}/lib/env.sh"
load_env_file "${ENV_FILE}"

: "${DOMAIN:?DOMAIN обязателен}"

# S38-002: допускаем секреты из файлов (Docker secrets/K8s). Если задан
# *_FILE, значение ENV может быть пустым — содержимое проверит приложение.
if [ -z "${SECRET_KEY:-}" ] && [ -z "${SECRET_KEY_FILE:-}" ]; then
    fail "нужен SECRET_KEY или SECRET_KEY_FILE"
fi
if [ -z "${SECRET_KEY_FILE:-}" ]; then
    [ "${#SECRET_KEY}" -ge 32 ] || fail "SECRET_KEY короче 32 символов"
    case "${SECRET_KEY}" in
        *change_me*) fail "SECRET_KEY содержит change_me — задайте случайный ключ" ;;
    esac
fi

if [ -z "${POSTGRES_PASSWORD:-}" ] && [ -z "${POSTGRES_PASSWORD_FILE:-}" ]; then
    fail "нужен POSTGRES_PASSWORD или POSTGRES_PASSWORD_FILE"
fi
if [ -z "${POSTGRES_PASSWORD_FILE:-}" ]; then
    case "${POSTGRES_PASSWORD}" in
        change_me*|password) fail "POSTGRES_PASSWORD не должен быть дефолтным" ;;
    esac
fi

case "${DOMAIN}" in
    teacher.example.com|example.com) fail "DOMAIN не заполнен (сейчас ${DOMAIN})" ;;
esac

compose() {
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

log "Проверка compose-конфигурации"
compose config --quiet || fail "docker compose config завершился ошибкой"

TAG="${IMAGE_TAG:-<из .env.prod>}"
log "Env: ${ENV_FILE}; compose: ${COMPOSE_FILE}; tag: ${TAG}"
log "Изображения:"
log "  backend:  ${BACKEND_IMAGE:-ghcr.io/${GHCR_OWNER:-iilmchat}/ai-teacher-backend:${IMAGE_TAG:-v0.6.0}}"
log "  frontend: ${FRONTEND_IMAGE:-ghcr.io/${GHCR_OWNER:-iilmchat}/ai-teacher-frontend:${IMAGE_TAG:-v0.6.0}}"
log "  sandbox:  ${SANDBOX_IMAGE:-ghcr.io/${GHCR_OWNER:-iilmchat}/ai-teacher-sandbox-runner:${IMAGE_TAG:-v0.6.0}}"

if [ "${DRY_RUN}" -eq 1 ]; then
    log "DRY-RUN: config валиден; бэкап/миграции/up/healthcheck не выполнялись"
    exit 0
fi

healthcheck() {
    local attempt=1
    while [ "${attempt}" -le "${HEALTH_RETRIES}" ]; do
        if [ -n "${HEALTH_URL}" ]; then
            if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
                log "Healthcheck OK (${HEALTH_URL})"
                return 0
            fi
        else
            if compose exec -T backend python -c \
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)" \
                >/dev/null 2>&1; then
                log "Healthcheck OK (/health/ready через backend)"
                return 0
            fi
        fi
        log "Healthcheck ${attempt}/${HEALTH_RETRIES} не прошёл, ждём ${HEALTH_INTERVAL}s"
        attempt=$((attempt + 1))
        sleep "${HEALTH_INTERVAL}"
    done
    return 1
}

record_state() {
    local backend_ref frontend_ref
    backend_ref="$(docker inspect --format '{{.Config.Image}}' "$(compose ps -q backend)")"
    frontend_ref="$(docker inspect --format '{{.Config.Image}}' "$(compose ps -q frontend)")"
    {
        echo "BACKEND_IMAGE=${backend_ref}"
        echo "FRONTEND_IMAGE=${frontend_ref}"
        echo "SANDBOX_IMAGE=${SANDBOX_IMAGE:-}"
        echo "IMAGE_TAG=${IMAGE_TAG:-}"
        echo "DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${STATE_FILE}.tmp"
    mv "${STATE_FILE}.tmp" "${STATE_FILE}"
    log "Состояние записано: ${STATE_FILE}"
}

# Предыдущее состояние — для авто-отката.
if [ -f "${STATE_FILE}" ]; then
    cp "${STATE_FILE}" "${LAST_FILE}"
    log "Предыдущее состояние сохранено: ${LAST_FILE}"
else
    log "Предыдущего состояния нет — авто-откат будет недоступен"
    rm -f "${LAST_FILE}"
fi

if [ "${NO_BACKUP}" -eq 0 ]; then
    log "Бэкап БД перед деплоем"
    if ! ENV_FILE="${ENV_FILE}" COMPOSE_FILE="${COMPOSE_FILE}" bash "${SCRIPT_DIR}/backup.sh"; then
        fail "Бэкап не удался — деплой остановлен (--no-backup, чтобы пропустить)"
    fi
else
    log "Бэкап пропущен (--no-backup)"
fi

on_error() {
    log "Деплой не удался; пробуем откат"
    if [ -f "${LAST_FILE}" ]; then
        ENV_FILE="${ENV_FILE}" COMPOSE_FILE="${COMPOSE_FILE}" \
            bash "${SCRIPT_DIR}/rollback.sh" --to "${LAST_FILE}" --no-pull || true
    else
        log "Нет ${LAST_FILE}: откат невозможен, требуется ручное вмешательство"
    fi
    exit 1
}

log "Поднимаем зависимости (postgres, redis)"
compose up -d --wait postgres redis || on_error

if [ "${SKIP_MIGRATIONS}" -eq 0 ]; then
    if [ "${NO_PULL}" -eq 0 ]; then
        log "Pull backend-образа (для миграций)"
        compose pull backend || on_error
    fi
    log "Миграции: alembic upgrade head (one-shot)"
    compose --profile tools run --rm migrate || on_error
else
    log "Миграции пропущены (--skip-migrations)"
fi

if [ "${NO_PULL}" -eq 0 ]; then
    log "Pull frontend-образа"
    compose pull frontend || on_error
fi

log "Обновление приложения"
compose up -d --no-deps --remove-orphans backend frontend caddy || on_error

log "Ожидание healthcheck"
healthcheck || on_error

record_state
log "OK: деплой завершён (tag=${IMAGE_TAG:-unknown})"
