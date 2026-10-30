#!/usr/bin/env bash
# CI: аудит backend-зависимостей (pip-audit по requirements.txt).
# --ignore-vuln: принятые residual-риски (KI-015/KI-016), синхронизировано с
# .github/workflows/ci.yml и docs/reports/sprint-20/SECURITY_AUDIT.md §8.
# После апгрейда starlette/pytest игноры удалить, иначе они скроют новые ID.
set -euo pipefail

python -m pip install --upgrade pip >/dev/null
pip install pip-audit >/dev/null

echo "==> pip-audit (backend/requirements.txt)"
pip-audit -r /src/backend/requirements.txt --strict --desc \
    --ignore-vuln PYSEC-2026-161 \
    --ignore-vuln PYSEC-2026-1941 \
    --ignore-vuln PYSEC-2026-1942 \
    --ignore-vuln PYSEC-2026-2280 \
    --ignore-vuln PYSEC-2026-2281 \
    --ignore-vuln PYSEC-2026-248 \
    --ignore-vuln PYSEC-2026-249 \
    --ignore-vuln PYSEC-2026-1845
echo "==> SECURITY BACKEND OK"
