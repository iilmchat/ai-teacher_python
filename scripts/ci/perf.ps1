# =============================================================================
# CI: perf-smoke песочницы (S23-003, KI-022).
#
# Поднимает backend на отдельном порту (8002) интерпретатором E2E_PYTHON,
# ждёт /health и прогоняет нагрузочный сценарий submit через
# backend/scripts/load_test.py. Бюджет задаётся сценарием (p95 ≤ 2000 мс),
# exit 1 при нарушении — job краснеет.
#
# PR:   -Rps 0.5 -Duration 20   (быстрый smoke, ~25 с)
# Ночь: -Rps 2   -Duration 60   (perf-nightly.yml)
#
# Требуемые env (как у e2e):
#   E2E_PYTHON           — путь к backend\venv\Scripts\python.exe
#   POSTGRES_PASSWORD    — пароль локального compose-Postgres
#   E2E_POSTGRES_PORT / E2E_REDIS_PORT — порты compose (KI-001)
# =============================================================================
param(
    [string]$Python = $env:E2E_PYTHON,
    [double]$Rps = 0.5,
    [int]$Duration = 20,
    [int]$Port = 8002,
    [string]$Scenario = 'submit',
    [string]$JsonOut = '',
    [string]$RepoRoot = $env:GITHUB_WORKSPACE
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
Set-Location $RepoRoot

if (-not $Python) {
    throw 'E2E_PYTHON не задан: нужен интерпретатор с зависимостями backend'
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "E2E_PYTHON указывает на несуществующий файл: $Python"
}
if (-not $env:POSTGRES_PASSWORD) {
    throw 'POSTGRES_PASSWORD не задан (secret репозитория)'
}

# Локальный compose-кластер (KI-001: канон 5434/6381 занят чужими контейнерами)
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = if ($env:E2E_POSTGRES_PORT) { $env:E2E_POSTGRES_PORT } else { '5434' }
$env:POSTGRES_USER = if ($env:E2E_POSTGRES_USER) { $env:E2E_POSTGRES_USER } else { 'ai_teacher' }
$env:POSTGRES_DB = if ($env:E2E_POSTGRES_DB) { $env:E2E_POSTGRES_DB } else { 'ai_teacher' }
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = if ($env:E2E_REDIS_PORT) { $env:E2E_REDIS_PORT } else { '6381' }

$env:DEBUG = 'false'
$env:LLM_PROVIDER = 'echo'
$env:RATE_LIMIT_ENABLED = 'false'
$env:SEED_ON_START = 'true'
$env:EXECUTOR_POOL_SIZE = '2'

$backend = Join-Path $RepoRoot 'backend'
$baseUrl = "http://127.0.0.1:$Port"

Write-Host "==> Postgres/Redis (docker compose): $env:POSTGRES_PORT/$env:REDIS_PORT"
# Отдельный compose-проект и имена контейнеров (docker-compose.ci.yml): иначе
# на машине с запущенным dev-стеком CI пересоздаст его контейнеры.
$env:COMPOSE_PROJECT_NAME = 'ai-teacher-ci'
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d postgres redis | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'docker compose up -d postgres redis failed' }

Write-Host "==> Миграции"
Push-Location $backend
try {
    & $Python -m alembic upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade head failed' }
} finally {
    Pop-Location
}

Write-Host "==> Backend на $baseUrl"
$backendProcess = Start-Process -FilePath $Python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port", '--log-level', 'warning') `
    -WorkingDirectory $backend -PassThru -WindowStyle Hidden

try {
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "$baseUrl/api/v1/health" -TimeoutSec 2
            if ($health) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { throw "backend не поднялся на $baseUrl за 30 с" }

    Write-Host "==> perf: scenario=$Scenario, duration=$Duration с, budgets из load_test.py"
    $loadArgs = @(
        (Join-Path $backend 'scripts\load_test.py'),
        '--scenario', $Scenario,
        '--duration', "$Duration",
        '--base-url', $baseUrl
    )
    if ($Scenario -eq 'submit' -and $Rps -gt 0) {
        $loadArgs += @('--rps', "$Rps")
    }
    if ($JsonOut) {
        $jsonPath = if ([System.IO.Path]::IsPathRooted($JsonOut)) { $JsonOut } else { Join-Path $RepoRoot $JsonOut }
        $jsonDir = Split-Path $jsonPath -Parent
        if ($jsonDir) { New-Item -ItemType Directory -Force $jsonDir | Out-Null }
        $loadArgs += @('--json-out', $jsonPath)
    }
    & $Python @loadArgs
    if ($LASTEXITCODE -ne 0) {
        throw "perf FAIL: scenario=$Scenario не уложился в бюджет p95/error rate"
    }
    Write-Host '==> PERF OK'
}
finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
