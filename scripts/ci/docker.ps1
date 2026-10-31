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

# S25: PyPI с машины проекта недоступен — образы собираются с зеркалом
# (переопределяется через CI_PYPI_MIRROR; на GitHub-hosted доступен pypi.org).
$pypiIndex = if ($env:CI_PYPI_MIRROR) { $env:CI_PYPI_MIRROR } else { 'https://mirrors.aliyun.com/pypi/simple/' }
Write-Host "==> индекс PyPI для сборки: $pypiIndex"

Write-Host '==> Сборка backend-образа'
docker build --build-arg "PIP_INDEX_URL=$pypiIndex" -t ai-teacher-backend ./backend
Assert-Step 'docker build ./backend'

Write-Host '==> Сборка frontend-образа'
docker build -t ai-teacher-frontend ./frontend
if ($LASTEXITCODE -ne 0) {
    Write-Warning "docker build ./frontend завершился с кодом $LASTEXITCODE — job продолжается (как continue-on-error в GitHub)"
}

# `:?` в prod-compose требует секреты; берём из CI, иначе — заглушки.
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = 'change_me_password' }
if (-not $env:SECRET_KEY) { $env:SECRET_KEY = 'ci_secret_key_do_not_use_in_production' }

# S24-001: образ контейнера-раннера песочницы собирается отдельно и проходит
# self-check изоляции (read-only rootfs, нет сети, нет capabilities, non-root).
Write-Host '==> Сборка образа контейнера-раннера (sandbox_runner)'
docker build --build-arg "PIP_INDEX_URL=$pypiIndex" -f ./backend/sandbox_runner/Dockerfile -t ai-teacher-sandbox-runner:latest ./backend
Assert-Step 'docker build sandbox_runner'

Write-Host '==> Self-check изоляции контейнера-раннера'
$sandboxCheck = docker run --rm -i `
    --network none --read-only --cap-drop ALL `
    --security-opt no-new-privileges --user 65534:65534 `
    --tmpfs /tmp:rw,noexec,nosuid,size=64m `
    --memory 128m --memory-swap 128m --pids-limit 64 --pull never `
    ai-teacher-sandbox-runner:latest --self-check
Assert-Step 'sandbox runner self-check'
$report = $sandboxCheck | ConvertFrom-Json
if (-not ($report.read_only_rootfs -and $report.tmp_writable -and
          $report.network_blocked -and $report.capabilities_zero)) {
    throw "self-check песочницы не прошёл: $sandboxCheck"
}
if ($report.uid -ne 65534) { throw "контейнер работает не под non-root: uid=$($report.uid)" }
Write-Host "    изоляция: read-only, network=none, caps=0, uid=$($report.uid)"

Write-Host '==> docker compose -f docker-compose.prod.yml config --quiet'
docker compose -f docker-compose.prod.yml config --quiet
Assert-Step 'docker compose config'

Write-Host '==> DOCKER OK'
