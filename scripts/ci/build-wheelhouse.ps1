# =============================================================================
# wheelhouse для офлайн-установки backend-зависимостей в CI (KI-017, S22-005).
#
# PyPI с машины проекта нестабилен, поэтому job'ы `lint`/`test`/`security`
# сначала берут колёса из named volume `ai-teacher-wheelhouse` (смонтирован в
# /wheelhouse), и только при его отсутствии идут в PyPI/зеркало.
#
# Обёртка над `scripts/wheelhouse.py`: скачивание выполняет Linux-контейнер
# (python:3.12-slim) — та же платформа, что у job'ов. Windows-wheelhouse,
# собранный pip'ом хоста, для контейнеров непригоден («not a supported wheel»).
#
# Примеры:
#   pwsh scripts/ci/build-wheelhouse.ps1                 # обновить volume
#   pwsh scripts/ci/build-wheelhouse.ps1 -Recreate       # с нуля
#   pwsh scripts/ci/build-wheelhouse.ps1 -ListOnly       # что лежит внутри
#   pwsh scripts/ci/build-wheelhouse.ps1 -IndexUrl https://pypi.org/simple/
# =============================================================================
param(
    [string]$Volume = 'ai-teacher-wheelhouse',
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$IndexUrl = 'https://mirrors.aliyun.com/pypi/simple/',
    [switch]$Recreate,
    [switch]$ListOnly
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker не найден в PATH (нужен Docker Desktop)'
}

if ($Recreate) {
    docker volume rm $Volume 2>$null | Out-Null
    Write-Host "==> volume $Volume пересоздаётся"
}

if ($ListOnly) {
    docker run --rm `
        -v "${Volume}:/wheelhouse:ro" `
        -v "${RepoRoot}:/src:ro" `
        python:3.12-slim `
        python /src/scripts/wheelhouse.py list --from /wheelhouse
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'backend\requirements.txt'))) {
    throw "requirements не найден: $RepoRoot\backend\requirements.txt"
}

Write-Host "==> скачивание колёс в volume $Volume (Linux-платформа контейнера)"
Write-Host "    индекс: $IndexUrl"
docker run --rm `
    -v "${Volume}:/wheelhouse" `
    -v "${RepoRoot}:/src:ro" `
    python:3.12-slim `
    python /src/scripts/wheelhouse.py build `
        --requirements /src/backend/requirements.txt `
        --out /wheelhouse `
        --index-url $IndexUrl

if ($LASTEXITCODE -ne 0) {
    throw "wheelhouse build не удался (индекс $IndexUrl, KI-017). Повторите позже, задайте -IndexUrl или соберите wheelhouse там, где PyPI доступен."
}

Write-Host '==> готово. Проверка:'
& $PSScriptRoot\build-wheelhouse.ps1 -Volume $Volume -RepoRoot $RepoRoot -ListOnly
