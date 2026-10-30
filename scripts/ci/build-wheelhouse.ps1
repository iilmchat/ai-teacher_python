# =============================================================================
# wheelhouse для офлайн-установки backend-зависимостей в CI (KI-017, S22-005).
#
# PyPI с машины проекта нестабилен, поэтому job'ы `lint`/`test` сначала берут
# колёса из named volume `ai-teacher-wheelhouse` (смонтирован в /wheelhouse),
# и только при его отсутствии идут в PyPI.
#
# ВАЖНО: колёса качает Linux-контейнер (python:3.12-slim) — та же платформа,
# что у job'ов. Windows-wheelhouse (собранный pip'ом хоста) для контейнеров
# непригоден: pip скажет «not a supported wheel».
#
# Примеры:
#   pwsh scripts/ci/build-wheelhouse.ps1                 # обновить volume
#   pwsh scripts/ci/build-wheelhouse.ps1 -Recreate       # с нуля
#   pwsh scripts/ci/build-wheelhouse.ps1 -ListOnly       # что лежит внутри
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
    docker run --rm -v "${Volume}:/wheelhouse:ro" python:3.12-slim `
        sh -c 'ls /wheelhouse/*.whl 2>/dev/null | wc -l; du -sh /wheelhouse 2>/dev/null'
    exit $LASTEXITCODE
}

$requirements = Join-Path $RepoRoot 'backend\requirements.txt'
if (-not (Test-Path -LiteralPath $requirements)) {
    throw "requirements не найден: $requirements"
}

Write-Host "==> скачивание колёс в volume $Volume (Linux/wheel платформа контейнера)"
Write-Host "    индекс: $IndexUrl"
$mirrorHost = ([uri]$IndexUrl).Host
docker run --rm `
    -v "${Volume}:/wheelhouse" `
    -v "${requirements}:/tmp/requirements.txt:ro" `
    python:3.12-slim `
    sh -c "pip download -q --timeout 30 --retries 3 --index-url '$IndexUrl' --trusted-host '$mirrorHost' -r /tmp/requirements.txt -d /wheelhouse && ls /wheelhouse/*.whl | wc -l"

if ($LASTEXITCODE -ne 0) {
    throw "pip download не удался (индекс $IndexUrl, KI-017). Повторите позже, задайте -IndexUrl или соберите wheelhouse там, где PyPI доступен."
}

Write-Host '==> готово. Проверка:'
& $PSScriptRoot\build-wheelhouse.ps1 -Volume $Volume -ListOnly
