# =============================================================================
# Сборка образа контейнера-раннера песочницы (S24-001).
#
# Контекст — backend/. Образ минимальный: python:3.12-slim + RestrictedPython +
# чистое ядро песочницы (без pydantic/sqlalchemy/БД).
#
# Примеры:
#   pwsh scripts/ci/build-sandbox-image.ps1
#   pwsh scripts/ci/build-sandbox-image.ps1 -Tag ai-teacher-sandbox-runner:dev
#   pwsh scripts/ci/build-sandbox-image.ps1 -SelfCheck
# =============================================================================
param(
    [string]$Tag = 'ai-teacher-sandbox-runner:latest',
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [switch]$SelfCheck
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker не найден в PATH (нужен Docker Desktop)'
}

Write-Host "==> Сборка $Tag (контекст: backend/)"
docker build -f sandbox_runner/Dockerfile -t $Tag (Join-Path $RepoRoot 'backend')
if ($LASTEXITCODE -ne 0) { throw "docker build не удался ($Tag)" }

Write-Host '==> Готово'

if ($SelfCheck) {
    Write-Host '==> Self-check изоляции'
    docker run --rm -i --network none --read-only --cap-drop ALL `
        --security-opt no-new-privileges --user 65534:65534 `
        --tmpfs /tmp:rw,noexec,nosuid,size=64m `
        --memory 128m --memory-swap 128m --pids-limit 64 --pull never `
        $Tag --self-check
    if ($LASTEXITCODE -ne 0) { throw 'self-check контейнера не удался' }
}
