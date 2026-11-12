#!/usr/bin/env bash
# Фиксация digest релизных образов в .env.prod (S36-002).
#
# После публикации тега (docker-publish.yml) скрипт получает immutable digest
# каждого образа и записывает полные ссылки:
#
#   BACKEND_IMAGE=ghcr.io/<owner>/ai-teacher-backend@sha256:...
#   FRONTEND_IMAGE=...
#   SANDBOX_IMAGE=...
#
# Запуск на машине с Docker и доступом к GHCR:
#   docker login ghcr.io -u <github-user> --password-stdin
#   bash scripts/pin_images.sh --tag v0.6.0
#
# Для тестов/CI без registry можно передать digest явно:
#   bash scripts/pin_images.sh --tag v0.6.0 \
#     --digest backend=sha256:... --digest frontend=sha256:... --digest sandbox=sha256:...
#
# Код возврата: 0 — успех; 1 — ошибка; 2 — неверные аргументы.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
GHCR_OWNER="${GHCR_OWNER:-iilmchat}"
TAG="${IMAGE_TAG:-}"
DRY_RUN=0
declare -A DIGEST_OVERRIDE=()

usage() {
    cat <<'EOF'
Фиксация digest образов в .env.prod.

Использование: bash scripts/pin_images.sh [опции]

  --tag TAG            тег релиза (по умолчанию IMAGE_TAG)
  --owner OWNER        владелец пакетов GHCR (по умолчанию GHCR_OWNER или iilmchat)
  --env-file FILE      файл, куда писать (по умолчанию .env.prod)
  --digest NAME=SHA    подставить digest без обращения к registry
                       (NAME: backend|frontend|sandbox)
  --dry-run            показать план, ничего не менять
  -h, --help           эта справка
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --tag) TAG="${2:-}"; shift 2 ;;
        --owner) GHCR_OWNER="${2:-}"; shift 2 ;;
        --env-file) ENV_FILE="${2:-}"; shift 2 ;;
        --digest)
            kv="${2:-}"
            [ -n "${kv}" ] || { echo "Ошибка: --digest требует NAME=SHA" >&2; exit 2; }
            DIGEST_OVERRIDE["${kv%%=*}"]="${kv#*=}"
            shift 2
            ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done

if [ -z "${TAG}" ]; then
    echo "Ошибка: не задан тег (--tag или IMAGE_TAG)" >&2
    exit 2
fi
if [ ! -f "${ENV_FILE}" ]; then
    echo "Ошибка: ${ENV_FILE} не найден (скопируйте .env.prod.example)" >&2
    exit 2
fi
if [ "${DRY_RUN}" -eq 0 ] && ! command -v docker >/dev/null 2>&1; then
    echo "Ошибка: docker не найден (нужен для buildx imagetools)" >&2
    exit 1
fi

resolve_digest() {
    local name="$1"
    local repo="$2"

    if [ -n "${DIGEST_OVERRIDE[${name}]:-}" ]; then
        printf '%s' "${DIGEST_OVERRIDE[${name}]}"
        return 0
    fi

    local ref="ghcr.io/${GHCR_OWNER}/${repo}:${TAG}"
    local digest=""

    if command -v docker >/dev/null 2>&1; then
        digest="$(docker buildx imagetools inspect "${ref}" \
            --format '{{.Manifest.Digest}}' 2>/dev/null || true)"
        if [ -z "${digest}" ]; then
            # Fallback: pull и RepoDigests (медленнее, но не требует buildx).
            docker pull "${ref}" >/dev/null 2>&1 || true
            digest="$(docker inspect --format '{{index .RepoDigests 0}}' "${ref}" 2>/dev/null \
                | sed 's/.*@//' || true)"
        fi
    fi

    if [ -z "${digest}" ] || [ "${digest}" = "<no value>" ]; then
        echo "Ошибка: не удалось получить digest для ${ref}" >&2
        echo "  Проверьте: docker login ghcr.io и что тег ${TAG} опубликован." >&2
        echo "  Для офлайн-теста: --digest ${name}=sha256:<64 hex>" >&2
        return 1
    fi
    case "${digest}" in
        sha256:*) printf '%s' "${digest}" ;;
        *) printf 'sha256:%s' "${digest}" ;;
    esac
}

set_var() {
    local key="$1" value="$2" file="$3"
    local tmp="${file}.tmp.$$"
    awk -v k="${key}" -v v="${value}" '
        BEGIN { done = 0 }
        index($0, k "=") == 1 { print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }
    ' "${file}" > "${tmp}"
    mv "${tmp}" "${file}"
}

declare -A REPO=(
    [backend]="ai-teacher-backend"
    [frontend]="ai-teacher-frontend"
    [sandbox]="ai-teacher-sandbox-runner"
)

if [ "${DRY_RUN}" -eq 1 ]; then
    echo "DRY-RUN: tag=${TAG}, owner=${GHCR_OWNER}, env=${ENV_FILE}"
    for name in backend frontend sandbox; do
        if [ -n "${DIGEST_OVERRIDE[${name}]:-}" ]; then
            echo "  ${name}: ghcr.io/${GHCR_OWNER}/${REPO[${name}]}@${DIGEST_OVERRIDE[${name}]}"
        else
            echo "  ${name}: ghcr.io/${GHCR_OWNER}/${REPO[${name}]}:${TAG} (digest будет получен)"
        fi
    done
    exit 0
fi

for name in backend frontend sandbox; do
    digest="$(resolve_digest "${name}" "${REPO[${name}]}")"
    ref="ghcr.io/${GHCR_OWNER}/${REPO[${name}]}@${digest}"
    key="$(echo "${name}" | tr '[:lower:]' '[:upper:]')_IMAGE"
    set_var "${key}" "${ref}" "${ENV_FILE}"
    echo "OK: ${key}=${ref}"
done

set_var "IMAGE_TAG" "${TAG}" "${ENV_FILE}"
echo "OK: обновлён ${ENV_FILE} (IMAGE_TAG=${TAG})"
