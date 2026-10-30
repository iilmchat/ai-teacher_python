# CI (self-hosted, Windows): e2e Playwright.
# Запускается напрямую на Windows-хосте runner'а (Docker Desktop, Node/pnpm,
# Playwright-браузеры в профиле пользователя). Backend поднимает webServer из
# frontend/playwright.config.ts интерпретатором E2E_PYTHON (venv основного
# checkout'а — PyPI на хосте заблокирован, KI-017).
#
# Требуемые env:
#   E2E_PYTHON         — абсолютный путь к backend\venv\Scripts\python.exe
#   POSTGRES_PASSWORD  — пароль локального compose-Postgres
# Опционально: E2E_POSTGRES_PORT / E2E_REDIS_PORT / E2E_POSTGRES_USER / E2E_POSTGRES_DB.
$ErrorActionPreference = 'Stop'

Set-Location $env:GITHUB_WORKSPACE

function Assert-Step([string]$Name) {
    if ($LASTEXITCODE -ne 0) {
        throw "Шаг '$Name' завершился с кодом $LASTEXITCODE"
    }
}

if (-not $env:E2E_PYTHON) {
    throw "E2E_PYTHON не задан. Задайте переменную репозитория E2E_PYTHON = <путь>\backend\venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $env:E2E_PYTHON)) {
    throw "E2E_PYTHON указывает на несуществующий файл: $env:E2E_PYTHON"
}
if (-not $env:POSTGRES_PASSWORD) {
    throw "POSTGRES_PASSWORD не задан (secret репозитория) — e2e не подключится к локальной БД"
}

Write-Host '==> Проверка локального Postgres/Redis (docker compose)'
docker compose up -d postgres redis
Assert-Step 'docker compose up -d postgres redis'

# CI=true: Playwright не переиспользует запущенные серверы, 1 retry, html-репорт.
$env:CI = 'true'
$env:RATE_LIMIT_ENABLED = 'false'
$env:LLM_PROVIDER = 'echo'
$env:DEBUG = 'false'
$env:E2E_DB_NAME = 'ai_teacher_e2e'
$env:E2E_BACKEND_PORT = '8001'
$env:E2E_FRONTEND_PORT = '3100'

$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = if ($env:E2E_POSTGRES_PORT) { $env:E2E_POSTGRES_PORT } else { '5434' }
$env:POSTGRES_USER = if ($env:E2E_POSTGRES_USER) { $env:E2E_POSTGRES_USER } else { 'ai_teacher' }
$env:POSTGRES_DB = if ($env:E2E_POSTGRES_DB) { $env:E2E_POSTGRES_DB } else { 'ai_teacher' }
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = if ($env:E2E_REDIS_PORT) { $env:E2E_REDIS_PORT } else { '6381' }

Write-Host '==> frontend: pnpm install'
Set-Location (Join-Path $env:GITHUB_WORKSPACE 'frontend')
pnpm install --frozen-lockfile --allow-build=esbuild
Assert-Step 'pnpm install'

Write-Host '==> Playwright e2e'
pnpm exec playwright test
Assert-Step 'playwright test'

Write-Host '==> E2E OK'
