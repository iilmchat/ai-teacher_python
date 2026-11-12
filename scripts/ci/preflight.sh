#!/bin/sh
# Preflight внутри CI-контейнера (S37-001/S37-003).
#
# Проверяет, что рабочая копия на месте, workspace записываемый и есть место
# на диске. Docker daemon внутри job-контейнера недоступен (socket не монтируется),
# его проверяет scripts/ci/preflight.ps1 на хосте раннера.
set -eu

fail() {
    echo "PREFLIGHT FAILED: $*" >&2
    exit 1
}

ROOT="${CI_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" || fail "не удалось перейти в $ROOT"
echo "==> preflight (container): cwd=$ROOT"

# 1. Ключевые файлы: неполный клон/неверный checkout.
for file in backend/requirements.txt gitflic-ci.yaml \
    scripts/ci/backend-lint.sh scripts/ci/backend-test.sh scripts/ci/frontend.sh; do
    [ -f "$file" ] || fail "нет обязательного файла: $file"
done

# 2. Workspace записываемый.
probe=".preflight-$$.tmp"
( : > "$probe" ) 2>/dev/null || fail "workspace не записывается: $ROOT"
rm -f "$probe"

# 3. Свободное место (минимум 2 ГБ).
MIN_GB="${CI_MIN_FREE_GB:-2}"
free_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
[ -n "$free_kb" ] || fail "не удалось определить свободное место"
free_gb=$((free_kb / 1024 / 1024))
if [ "$free_gb" -lt "$MIN_GB" ]; then
    fail "мало места: ${free_gb} ГБ < ${MIN_GB} ГБ"
fi

echo "==> preflight OK (${free_gb} ГБ свободно)"
