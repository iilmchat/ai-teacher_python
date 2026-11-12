# Единый локальный прогон гейтов (S37-005), Windows/PowerShell.
#
#   pwsh -File scripts/ci/gates.ps1             # fast: lint/type/unit
#   pwsh -File scripts/ci/gates.ps1 -Full       # + coverage/e2e/compose/promtool
#   pwsh -File scripts/ci/gates.ps1 -Full -Json # + gates-report.json
#
# Не останавливается на первом падении: собирает сводку и возвращает 1, если
# хоть один шаг упал. `-Ci` — без интерактива (флаг для совместимости).

[CmdletBinding()]
param(
    [switch]$Full,
    [switch]$Ci,
    [switch]$Json
)

$ErrorActionPreference = 'Continue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root

$steps = [System.Collections.Generic.List[object]]::new()
$failed = $false

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)

    Write-Host ""
    Write-Host "==> [$Name]"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $ok = $true
    try {
        & $Action
        if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) { $ok = $false }
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        $ok = $false
    }
    $sw.Stop()
    $script:steps.Add([pscustomobject]@{
        name = $Name
        status = if ($ok) { 'ok' } else { 'failed' }
        duration_s = [math]::Round($sw.Elapsed.TotalSeconds)
    })
    if (-not $ok) { $script:failed = $true }
    Write-Host ("<== [{0}] {1} ({2}s)" -f $Name, $(if ($ok) { 'ok' } else { 'failed' }), [math]::Round($sw.Elapsed.TotalSeconds))
}

Invoke-Step 'image-pins' { python backend/scripts/check_image_pins.py }
Invoke-Step 'ci-parity' { python scripts/ci/check_ci_parity.py }
Invoke-Step 'env-drift' { python scripts/check_env_drift.py }
Invoke-Step 'backend-lint' { Push-Location backend; try { ruff check app tests scripts } finally { Pop-Location } }
Invoke-Step 'backend-mypy' { Push-Location backend; try { python -m mypy app } finally { Pop-Location } }
Invoke-Step 'frontend-typecheck' { Push-Location frontend; try { pnpm typecheck } finally { Pop-Location } }
Invoke-Step 'frontend-lint' { Push-Location frontend; try { pnpm lint } finally { Pop-Location } }

if ($Full) {
    Invoke-Step 'backend-tests' {
        Push-Location backend
        try { python -m pytest -q --cov=app --cov-report=term --cov-fail-under=70 } finally { Pop-Location }
    }
    Invoke-Step 'frontend-tests' { Push-Location frontend; try { pnpm test:coverage } finally { Pop-Location } }
    Invoke-Step 'frontend-build' { Push-Location frontend; try { pnpm build } finally { Pop-Location } }
    Invoke-Step 'compose-config' {
        docker compose --env-file .env.prod.example -f docker-compose.prod.yml config --quiet
    }
    Invoke-Step 'promtool' { pwsh -NoProfile -File ./scripts/monitoring/validate_prometheus.ps1 }
    Invoke-Step 'e2e' { Push-Location frontend; try { pnpm e2e } finally { Pop-Location } }
} else {
    Invoke-Step 'frontend-unit' { Push-Location frontend; try { pnpm test } finally { Pop-Location } }
}

Write-Host ""
Write-Host ("=== gates summary ({0}) ===" -f $(if ($Full) { 'full' } else { 'fast' }))
foreach ($step in $steps) {
    Write-Host ("  {0,-20} {1,-8} {2}s" -f $step.name, $step.status, $step.duration_s)
}

if ($Json) {
    $report = [pscustomobject]@{
        mode = if ($Full) { 'full' } else { 'fast' }
        steps = $steps
        ok = -not $failed
    }
    $path = Join-Path $root 'gates-report.json'
    $report | ConvertTo-Json -Depth 5 | Set-Content -Path $path -Encoding utf8
    Write-Host "JSON: $path"
}

if ($failed) {
    Write-Host 'FAILED: есть красные гейты' -ForegroundColor Red
    exit 1
}
Write-Host 'OK: все гейты зелёные'
exit 0
