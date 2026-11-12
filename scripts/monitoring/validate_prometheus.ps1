# Валидация Prometheus-конфига и правил (S35-003), Windows-версия.
# Использует локальный promtool или Docker-образ.
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$promVersion = if ($env:PROMETHEUS_VERSION) { $env:PROMETHEUS_VERSION } else { 'v3.5.0' }
$promDir = Join-Path $root 'deploy\monitoring\prometheus'

function Invoke-Promtool {
    param([string[]]$Arguments)

    $promtool = Get-Command promtool -ErrorAction SilentlyContinue
    if ($promtool) {
        & $promtool.Source @Arguments
        if ($LASTEXITCODE -ne 0) { throw "promtool exit $LASTEXITCODE" }
        return
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Ни promtool, ни docker не найдены'
    }

    docker run --rm -v "${promDir}:/etc/prometheus:ro" --entrypoint promtool `
        "prom/prometheus:$promVersion" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "promtool (docker) exit $LASTEXITCODE" }
}

Invoke-Promtool @('check', 'config', '/etc/prometheus/prometheus.yml')
Invoke-Promtool @(
    'check', 'rules',
    '/etc/prometheus/rules/alerts.yml',
    '/etc/prometheus/rules/recording.yml'
)

python (Join-Path $root 'scripts\monitoring\validate_dashboards.py')
if ($LASTEXITCODE -ne 0) { throw "validate_dashboards exit $LASTEXITCODE" }

Write-Host 'OK: Prometheus rules и Grafana dashboards валидны'
