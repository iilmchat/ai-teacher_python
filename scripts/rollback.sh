#!/usr/bin/env bash
# Откат приложения на предыдущее состояние (S36-005).
#
# Использует `.last_deploy` (состояние до последнего деплоя): полные ссылки
# образов (tag/digest) и IMAGE_TAG. Схема БД не откатывается — миграции
# аддитивные; при необходимости восстановления данных используйте restore.sh.
#
# Использование:
#   bash scripts/rollback.sh                  # на .last_deploy
#   bash scripts/rollback.sh --to FILE        # на конкретное состояние
#   bash scripts/rollback.sh --dry-run
#
# Код возврата: 0 — успех; 1 — ошибка/healthcheck; 2 — аргументы/состояние.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
TO_FILE="${DEPLOY_LAST:-${ROOT_DIR}/.last_deploy}"
STATE_FILE="${DEPLOY_STATE:-${ROOT_DIR}/.deploy-state}"
HEALTH_RETRIES="${DEPLOY_HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${DEPLOY_HEALTH_INTERVAL:-2}"
HEALTH_URL="${DEPLOY_HEALTHCHECK_URL:-}"

DRY_RUN=0
NO_PULL=0

usage() {
    cat <<'EOF'
Откат на предыдущие образы из .last_deploy.

Использование: bash scripts/rollback.sh [опции]

  --to FILE       файл состояния (default: .last_deploy)
  --no-pull       не делать pull (образы уже локально)
  --dry-run       показать план, ничего не менять
  -h, --help      эта справка
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --to) TO_FILE="${2:-}"; shift 2 ;;
        --no-pull) NO_PULL=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

log() { printf '[rollback] %s\n' "$*"; }
fail() { printf '[rollback] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker не найден"
[ -f "${ENV_FILE}" ] || fail "${ENV_FILE} не найден"
[ -f "${COMPOSE_FILE}" ] || fail "${COMPOSE_FILE} не найден"
[ -f "${TO_FILE}" ] || fail "состояние ${TO_FILE} не найдено (нечего откатывать)"

# shellcheck source=lib/env.sh
. "${SCRIPT_DIR}/lib/env.sh"
load_env_file "${ENV_FILE}"
load_env_file "${TO_FILE}"

[ -n "${BACKEND_IMAGE:-}" ] || fail "в ${TO_FILE} нет BACKEND_IMAGE"
[ -n "${FRONTEND_IMAGE:-}" ] || fail "в ${TO_FILE} нет FRONTEND_IMAGE"

export BACKEND_IMAGE FRONTEND_IMAGE
if [ -n "${SANDBOX_IMAGE:-}" ]; then
    export SANDBOX_IMAGE
fi

compose() {
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

log "Откат на состояние ${TO_FILE}"
log "  backend:  ${BACKEND_IMAGE}"
log "  frontend: ${FRONTEND_IMAGE}"
log "  tag:      ${IMAGE_TAG:-unknown}, deployed_at: ${DEPLOYED_AT:-unknown}"

compose config --quiet || fail "docker compose config завершился ошибкой"

if [ "${DRY_RUN}" -eq 1 ]; then
    log "DRY-RUN: откат не выполнялся"
    exit 0
fi

if [ "${NO_PULL}" -eq 0 ]; then
    log "Pull образов предыдущего релиза"
    compose pull backend frontend || fail "pull не удался"
fi

log "Перезапуск backend/frontend/caddy"
compose up -d --no-deps --remove-orphans backend frontend caddy \
    || fail "up не удался"

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

healthcheck || fail "после отката healthcheck не прошёл"

cp "${TO_FILE}" "${STATE_FILE}"
log "OK: откат завершён; ${STATE_FILE} обновлён"
