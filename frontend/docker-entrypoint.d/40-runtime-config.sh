#!/bin/sh
# S35-002: runtime-конфиг frontend. Официальный nginx-образ выполняет скрипты
# из /docker-entrypoint.d/ перед стартом; здесь пишем /config.js из ENV,
# чтобы один и тот же образ работал с разными DSN/окружениями без пересборки.
set -e

CONFIG_PATH="/usr/share/nginx/html/config.js"

escape_js() {
    # экранируем backslash, двойные кавычки и переводы строк
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n' ' '
}

SENTRY_DSN_ESCAPED="$(escape_js "${SENTRY_DSN:-}")"
SENTRY_ENV_ESCAPED="$(escape_js "${SENTRY_ENVIRONMENT:-production}")"
RELEASE_ESCAPED="$(escape_js "${APP_RELEASE:-}")"
TRACES_RATE="${SENTRY_TRACES_SAMPLE_RATE:-0}"

cat > "$CONFIG_PATH" <<EOF
// Сгенерировано docker-entrypoint (S35-002). Не редактировать в контейнере.
window.__APP_CONFIG__ = {
  sentryDsn: "${SENTRY_DSN_ESCAPED}",
  sentryEnvironment: "${SENTRY_ENV_ESCAPED}",
  release: "${RELEASE_ESCAPED}",
  sentryTracesSampleRate: ${TRACES_RATE},
};
EOF

echo "docker-entrypoint: runtime config written to $CONFIG_PATH"
