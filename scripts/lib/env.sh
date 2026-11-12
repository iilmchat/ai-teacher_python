#!/usr/bin/env bash
# Безопасная загрузка KEY=VALUE из env-файла без `source`.
#
# `source .env` ломается на значениях с пробелами (`APP_NAME=AI Teacher ...`)
# и исполняет содержимое файла. Здесь строки разбираются как данные.
#
# Использование:
#   . "$(dirname "$0")/lib/env.sh"
#   load_env_file .env.prod

load_env_file() {
    local file="$1"
    [ -f "${file}" ] || return 0

    local line key value
    while IFS= read -r line || [ -n "${line}" ]; do
        line="${line%$'\r'}"
        case "${line}" in
            ''|\#*) continue ;;
        esac
        case "${line}" in
            *=*) ;;
            *) continue ;;
        esac
        key="${line%%=*}"
        value="${line#*=}"
        # только валидные имена переменных
        case "${key}" in
            *[!A-Za-z0-9_]*|'') continue ;;
        esac
        export "${key}=${value}"
    done < "${file}"
}
