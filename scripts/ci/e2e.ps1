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

# Порты резолвим ДО compose: на машине проекта канон 5434/6381 занят чужими
# контейнерами (KI-001), поэтому значения приходят из переменных репозитория
# E2E_POSTGRES_PORT / E2E_REDIS_PORT и должны совпасть у compose и у тестов.
$pgPort = if ($env:E2E_POSTGRES_PORT) { $env:E2E_POSTGRES_PORT } else { '5434' }
$redisPort = if ($env:E2E_REDIS_PORT) { $env:E2E_REDIS_PORT } else { '6381' }
$pgUser = if ($env:E2E_POSTGRES_USER) { $env:E2E_POSTGRES_USER } else { 'ai_teacher' }
$pgDb = if ($env:E2E_POSTGRES_DB) { $env:E2E_POSTGRES_DB } else { 'ai_teacher' }

Write-Host "==> Локальный Postgres/Redis: $pgPort/$redisPort (docker compose)"
# compose читает .env, но в clone'е runner'а его нет (файл в .gitignore) —
# поэтому пробрасываем значения явно через окружение процесса.
$env:POSTGRES_PORT = $pgPort
$env:REDIS_PORT = $redisPort
$env:POSTGRES_USER = $pgUser
$env:POSTGRES_DB = $pgDb
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
$env:REDIS_HOST = '127.0.0.1'

Write-Host '==> frontend: pnpm install'
Set-Location (Join-Path $env:GITHUB_WORKSPACE 'frontend')
pnpm install --frozen-lockfile --allow-build=esbuild
Assert-Step 'pnpm install'

Write-Host '==> Playwright e2e'
pnpm exec playwright test
Assert-Step 'playwright test'

Write-Host '==> E2E OK'
