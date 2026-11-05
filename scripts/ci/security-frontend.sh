#!/usr/bin/env bash
# CI: аудит frontend-зависимостей (pnpm audit по lockfile).
# High/critical блокируют, dev-only moderate — нет (как в GitHub/GitFlic).
set -euo pipefail

WORKSPACE=/workspace
mkdir -p "$WORKSPACE"
cd /src
tar --exclude=frontend/node_modules \
    --exclude=frontend/dist \
    --exclude=frontend/public/monaco \
    -cf - frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml 2>/dev/null \
    | tar -xf - -C "$WORKSPACE" || true
cd "$WORKSPACE/frontend" 2>/dev/null || { echo "frontend-манифесты не найдены"; exit 1; }

corepack enable
corepack prepare pnpm@12 --activate || corepack install --global pnpm@12

echo "==> pnpm audit --audit-level=high"
pnpm audit --audit-level=high
echo "==> SECURITY FRONTEND OK"
