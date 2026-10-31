# CI (self-hosted, Windows): сборка Docker-образов и валидация prod-compose.
# Использует Docker Desktop хоста (как GitFlic-job `docker`).
$ErrorActionPreference = 'Stop'

Set-Location $env:GITHUB_WORKSPACE

function Assert-Step([string]$Name) {
    if ($LASTEXITCODE -ne 0) {
        throw "Шаг '$Name' завершился с кодом $LASTEXITCODE"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker CLI не найден в PATH (Docker Desktop не установлен/не в PATH)"
}

Write-Host '==> Проверка Docker daemon'
docker info --format '{{.ServerVersion}}' | Out-Null
Assert-Step 'docker info (Docker Desktop запущен?)'

Write-Host '==> Сборка backend-образа'
docker build -t ai-teacher-backend ./backend
Assert-Step 'docker build ./backend'

Write-Host '==> Сборка frontend-образа'
docker build -t ai-teacher-frontend ./frontend
if ($LASTEXITCODE -ne 0) {
    Write-Warning "docker build ./frontend завершился с кодом $LASTEXITCODE — job продолжается (как continue-on-error в GitHub)"
}

# `:?` в prod-compose требует секреты; берём из CI, иначе — заглушки.
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = 'change_me_password' }
if (-not $env:SECRET_KEY) { $env:SECRET_KEY = 'ci_secret_key_do_not_use_in_production' }

Write-Host '==> docker compose -f docker-compose.prod.yml config --quiet'
docker compose -f docker-compose.prod.yml config --quiet
Assert-Step 'docker compose config'

Write-Host '==> DOCKER OK'
