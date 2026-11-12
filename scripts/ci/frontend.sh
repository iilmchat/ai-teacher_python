#!/usr/bin/env bash
# CI: frontend (typecheck/lint/unit/build) в node:22-alpine.
# Копируем frontend в /workspace, чтобы не писать node_modules в read-only /src.
set -euo pipefail

WORKSPACE=/workspace
mkdir -p "$WORKSPACE"
cd /src
tar --exclude=frontend/node_modules \
    --exclude=frontend/dist \
    --exclude=frontend/public/monaco \
    --exclude=frontend/.pnpm-store \
    --exclude=frontend/playwright-report \
    --exclude=frontend/test-results \
    -cf - frontend | tar -xf - -C "$WORKSPACE"
cd "$WORKSPACE/frontend"

# pnpm 12: corepack из Node 22; настройки build-скриптов — в pnpm-workspace.yaml
# (RULES §11.10). `prepare` — основной способ, `install --global` — fallback.
corepack enable
corepack prepare pnpm@12 --activate || corepack install --global pnpm@12
pnpm --version

echo "==> pnpm install"
pnpm install --frozen-lockfile --allow-build=esbuild --store-dir .pnpm-store
echo "==> typecheck"
pnpm typecheck
echo "==> lint"
pnpm lint
echo "==> i18n audit (S29-002)"
node scripts/check-i18n.mjs
echo "==> unit tests (vitest, coverage gate)"
pnpm test:coverage
echo "==> build"
pnpm build
echo "==> FRONTEND OK"
