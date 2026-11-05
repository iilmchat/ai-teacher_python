#!/usr/bin/env bash
# CI: аудит backend-зависимостей (pip-audit по requirements.txt).
#
# Аудит без игноров: S22-002 закрыл 7 advisory starlette (fastapi 0.162 +
# starlette 1.10), S22-003 — dev-only pytest (9.2). Остались только находки,
# которые появятся в будущем, — их job должен ловить, а не игнорировать.
#
# Сеть (KI-017): pypi.org с машины проекта недоступен/нестабилен, поэтому
#   1) pip-audit ставим из wheelhouse, иначе из зеркала, и только последним —
#      из pypi.org (иначе job залипает на TLS-таймаутах);
#   2) метаданные пакетов pip-audit резолвит через то же зеркало (`--index-url`);
#   3) если pypi.org не отвечает, advisory-сервис переключается на OSV
#      (api.osv.dev) — тот же набор PYSEC/GHSA (проверено 2026-10-30:
#      «No known vulnerabilities found, 16 ignored», exit 0).
set -euo pipefail

MIRROR="${CI_PYPI_MIRROR:-https://mirrors.aliyun.com/pypi/simple/}"
MIRROR_FALLBACK="${CI_PYPI_MIRROR_FALLBACK:-https://pypi.tuna.tsinghua.edu.cn/simple/}"
WHEELHOUSE="${CI_WHEELHOUSE:-/wheelhouse}"

installed=0
if [ -d "$WHEELHOUSE" ] && compgen -G "$WHEELHOUSE/pip_audit*.whl" > /dev/null; then
    echo "==> pip-audit из wheelhouse ($WHEELHOUSE)"
    pip install --no-index --find-links "$WHEELHOUSE" pip-audit > /dev/null && installed=1
fi
if [ "$installed" -eq 0 ]; then
    echo "==> pip-audit из зеркала $MIRROR"
    pip install -q --index-url "$MIRROR" pip-audit > /dev/null && installed=1
fi
if [ "$installed" -eq 0 ]; then
    echo "==> pip-audit из зеркала $MIRROR_FALLBACK"
    pip install -q --index-url "$MIRROR_FALLBACK" pip-audit > /dev/null && installed=1
fi
if [ "$installed" -eq 0 ]; then
    echo "==> pip-audit из pypi.org (последняя попытка)"
    pip install -q pip-audit > /dev/null && installed=1
fi
if [ "$installed" -eq 0 ]; then
    echo "!! pip-audit поставить не удалось: wheelhouse и зеркала недоступны (KI-017)" >&2
    exit 1
fi

# Индекс для резолва requirements — тот же, что сработал (по умолчанию aliyun).
if ! python -c "import urllib.request; urllib.request.urlopen('$MIRROR', timeout=8)" 2>/dev/null; then
    echo "==> основное зеркало недоступно, используем $MIRROR_FALLBACK"
    MIRROR="$MIRROR_FALLBACK"
fi

VULN_ARGS=()
if ! python -c "import urllib.request; urllib.request.urlopen('https://pypi.org/pypi/pip/json', timeout=5)" 2>/dev/null; then
    echo "==> pypi.org недоступен — advisory-сервис OSV"
    VULN_ARGS=(--vulnerability-service osv)
fi

echo "==> pip-audit (backend/requirements.txt)"
pip-audit -r /src/backend/requirements.txt --strict --desc \
    --index-url "$MIRROR" "${VULN_ARGS[@]}"
echo "==> SECURITY BACKEND OK"
