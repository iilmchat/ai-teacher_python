#!/usr/bin/env bash
# Установка backend-зависимостей в python:3.12-slim (общая для lint и test).
#
# Порядок попыток:
#   1) wheelhouse (named volume /wheelhouse, смонтирован read-only) — офлайн,
#      основной путь на self-hosted runner'е (KI-017);
#   2) PyPI напрямую;
#   3) зеркало PyPI (aliyun/tsinghua) — когда pypi.org с машины недоступен:
#      TLS-хендшейк «залипает», а зеркала отвечают (проверено 2026-10-30).
#
# Переопределение: CI_PYPI_MIRROR / CI_PYPI_MIRROR_FALLBACK,
# CI_WHEELHOUSE (по умолчанию /wheelhouse).
#
# Использование: bash install-python-deps.sh <path-to-requirements.txt>
set -euo pipefail

REQUIREMENTS="${1:-/workspace/backend/requirements.txt}"
WHEELHOUSE="${CI_WHEELHOUSE:-/wheelhouse}"
MIRROR="${CI_PYPI_MIRROR:-https://mirrors.aliyun.com/pypi/simple/}"
MIRROR_FALLBACK="${CI_PYPI_MIRROR_FALLBACK:-https://pypi.tuna.tsinghua.edu.cn/simple/}"

# Нестабильный PyPI: короткие таймауты, чтобы быстро уйти на зеркало (§12.5 CI.md).
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-30}"
export PIP_RETRIES="${PIP_RETRIES:-2}"

if [ ! -f "$REQUIREMENTS" ]; then
    echo "!! requirements не найден: $REQUIREMENTS" >&2
    exit 2
fi

# pip в python:3.12-slim достаточно свежий; --upgrade pip требует сети — не обновляем.

if [ -d "$WHEELHOUSE" ] && compgen -G "$WHEELHOUSE/*.whl" > /dev/null; then
    echo "==> зависимости из wheelhouse ($WHEELHOUSE), без сети"
    if pip install --no-index --find-links "$WHEELHOUSE" -r "$REQUIREMENTS" > /dev/null; then
        echo "==> wheelhouse OK"
        exit 0
    fi
    echo "!! офлайн-установка не удалась: wheelhouse неполный или для другой ОС"
    echo "   пересоберите: pwsh scripts/ci/build-wheelhouse.ps1"
    echo "   fallback: индекс PyPI (сеть)"
fi

echo "==> зависимости из pypi.org"
if pip install -r "$REQUIREMENTS" > /dev/null; then
    echo "==> pypi.org OK"
    exit 0
fi

for index in "$MIRROR" "$MIRROR_FALLBACK"; do
    [ -n "$index" ] || continue
    echo "==> pypi.org недоступен, пробуем зеркало: $index"
    host="$(printf '%s' "$index" | sed -E 's#^https?://([^/]+).*#\1#')"
    if pip install -r "$REQUIREMENTS" --index-url "$index" --trusted-host "$host" > /dev/null; then
        echo "==> зеркало $host OK"
        exit 0
    fi
done

echo "!! не удалось поставить зависимости: PyPI и зеркала недоступны (KI-017)" >&2
exit 1
