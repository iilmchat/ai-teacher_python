#!/bin/sh
# Валидация Prometheus-конфига и правил (S35-003).
# Использует локальный promtool или Docker-образ (если promtool не установлен).
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
PROMETHEUS_VERSION="${PROMETHEUS_VERSION:-v3.5.0}"

if command -v promtool >/dev/null 2>&1; then
    echo "promtool: $(promtool --version | head -n 1)"
    promtool check config "$ROOT/deploy/monitoring/prometheus/prometheus.yml"
    promtool check rules \
        "$ROOT/deploy/monitoring/prometheus/rules/alerts.yml" \
        "$ROOT/deploy/monitoring/prometheus/rules/recording.yml"
elif command -v docker >/dev/null 2>&1; then
    echo "promtool: docker prom/prometheus:${PROMETHEUS_VERSION}"
    docker run --rm \
        -v "$ROOT/deploy/monitoring/prometheus:/etc/prometheus:ro" \
        --entrypoint promtool \
        "prom/prometheus:${PROMETHEUS_VERSION}" \
        check config /etc/prometheus/prometheus.yml
    docker run --rm \
        -v "$ROOT/deploy/monitoring/prometheus:/etc/prometheus:ro" \
        --entrypoint promtool \
        "prom/prometheus:${PROMETHEUS_VERSION}" \
        check rules /etc/prometheus/rules/alerts.yml /etc/prometheus/rules/recording.yml
else
    echo "ERROR: ни promtool, ни docker не найдены" >&2
    exit 2
fi

python "$ROOT/scripts/monitoring/validate_dashboards.py"
echo "OK: Prometheus rules и Grafana dashboards валидны"
