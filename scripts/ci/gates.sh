#!/usr/bin/env bash
# Единый локальный прогон гейтов (S37-005).
#
#   bash scripts/ci/gates.sh --fast            # lint/type/unit
#   bash scripts/ci/gates.sh --full --ci       # всё, что умеет CI
#   bash scripts/ci/gates.sh --full --json     # + gates-report.json
#
# Не останавливается на первом падении: собирает сводку и возвращает 1, если
# хоть один шаг упал. `--ci` — без интерактива (сейчас поведение одинаковое,
# флаг оставлен для совместимости с RULES §10).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MODE="fast"
AS_CI=0
JSON=0

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --fast) MODE="fast"; shift ;;
        --full) MODE="full"; shift ;;
        --ci) AS_CI=1; shift ;;
        --json) JSON=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ошибка: неизвестный аргумент: $1" >&2; usage; exit 2 ;;
    esac
done
: "${AS_CI:=0}"

cd "$ROOT"
NAMES=()
STATUSES=()
DURATIONS=()
FAILED=0

run_step() {
    local name="$1"; shift
    local start end status
    start=$(date +%s)
    echo ""
    echo "==> [$name] $*"
    if "$@"; then
        status="ok"
    else
        status="failed"
        FAILED=1
    fi
    end=$(date +%s)
    NAMES+=("$name")
    STATUSES+=("$status")
    DURATIONS+=("$((end - start))")
    echo "<== [$name] $status ($((end - start))s)"
}

run_step "image-pins" python backend/scripts/check_image_pins.py
run_step "ci-parity" python scripts/ci/check_ci_parity.py
run_step "env-drift" python scripts/check_env_drift.py
run_step "backend-lint" bash -c "cd backend && ruff check app tests scripts"
run_step "backend-mypy" bash -c "cd backend && python -m mypy app"
run_step "frontend-typecheck" bash -c "cd frontend && pnpm typecheck"
run_step "frontend-lint" bash -c "cd frontend && pnpm lint"

if [ "$MODE" = "full" ]; then
    run_step "backend-tests" bash -c \
        "cd backend && python -m pytest -q --cov=app --cov-report=term --cov-fail-under=70"
    run_step "frontend-tests" bash -c "cd frontend && pnpm test:coverage"
    run_step "frontend-build" bash -c "cd frontend && pnpm build"
    run_step "compose-config" bash -c \
        "docker compose --env-file .env.prod.example -f docker-compose.prod.yml config --quiet"
    run_step "promtool" bash scripts/monitoring/validate_prometheus.sh
    run_step "e2e" bash -c "cd frontend && pnpm e2e"
else
    run_step "frontend-unit" bash -c "cd frontend && pnpm test"
fi

echo ""
echo "=== gates summary (${MODE}) ==="
for i in "${!NAMES[@]}"; do
    printf '  %-20s %-8s %ss\n' "${NAMES[$i]}" "${STATUSES[$i]}" "${DURATIONS[$i]}"
done

if [ "$JSON" -eq 1 ]; then
    {
        echo "{"
        echo "  \"mode\": \"${MODE}\","
        echo "  \"steps\": ["
        for i in "${!NAMES[@]}"; do
            comma=","
            [ "$i" -eq $((${#NAMES[@]} - 1)) ] && comma=""
            printf '    {"name": "%s", "status": "%s", "duration_s": %s}%s\n' \
                "${NAMES[$i]}" "${STATUSES[$i]}" "${DURATIONS[$i]}" "$comma"
        done
        echo "  ],"
        echo "  \"ok\": $([ "$FAILED" -eq 0 ] && echo true || echo false)"
        echo "}"
    } > gates-report.json
    echo "JSON: ${ROOT}/gates-report.json"
fi

[ "$FAILED" -eq 0 ] && echo "OK: все гейты зелёные" || echo "FAILED: есть красные гейты" >&2
exit "$FAILED"
