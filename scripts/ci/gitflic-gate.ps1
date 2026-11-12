# GitFlic merge-gate: проверка локального пайплайна и чек-лист настройки (S37-002).
#
# GitFlic API защиты ветвей зависит от версии/тарифа и требует токена
# владельца, которого у агента нет. Скрипт:
#   1. проверяет, что в gitflic-ci.yaml есть обязательные job'ы;
#   2. печатает пошаговую инструкцию для UI GitFlic;
#   3. после ручной настройки помогает проверить гейт красным MR.
#
# Использование:
#   pwsh -NoProfile -File scripts/ci/gitflic-gate.ps1
#   pwsh -NoProfile -File scripts/ci/gitflic-gate.ps1 -Json   # машинный вывод

[CmdletBinding()]
param(
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pipeline = Join-Path $root 'gitflic-ci.yaml'

if (-not (Test-Path -LiteralPath $pipeline)) {
    throw "gitflic-ci.yaml не найден: $pipeline"
}

$text = Get-Content -LiteralPath $pipeline -Raw
$jobMatches = [regex]::Matches($text, '(?m)^([A-Za-z0-9_-]+):\s*$')
$nonJobs = @('stages', 'variables', 'workflow', 'include', 'default')
$jobs = @(
    $jobMatches |
        ForEach-Object { $_.Groups[1].Value } |
        Where-Object { $nonJobs -notcontains $_ } |
        Sort-Object -Unique
)

$required = @('lint', 'test', 'frontend', 'security-backend', 'security-frontend', 'gitleaks')
$missing = @($required | Where-Object { $jobs -notcontains $_ })
$ok = $missing.Count -eq 0

$result = [ordered]@{
    pipeline = $pipeline
    jobs = $jobs
    required = $required
    missing = $missing
    ok = $ok
    manual_steps = @(
        'GitFlic → проект → Settings → CI/CD: включить "Enable Merge Request Pipeline" (и, при доступности, merge-result pipeline).',
        'Branches / Защита ветвей: для main запретить force-push и прямые push, разрешить только Merge Request.',
        'Включить опцию "Проверять статус последнего конвейера при слиянии" (или аналог required pipeline status).',
        'Required jobs: lint, test, frontend, security-backend, security-frontend, gitleaks.',
        'Проверка: MR с намеренно падающим job (например, ruff) — кнопка Merge недоступна; после исправления — доступна.',
        'Записать результат проверки в docs/KNOWN_ISSUES.md (KI-023) с датой и платформой.'
    )
}

if ($Json) {
    $result | ConvertTo-Json -Depth 5
} else {
    Write-Host '==> GitFlic merge-gate (S37-002)'
    Write-Host "Pipeline: $pipeline"
    Write-Host "Jobs: $($jobs -join ', ')"
    if (-not $ok) {
        Write-Host "MISSING required jobs: $($missing -join ', ')" -ForegroundColor Red
    }
    Write-Host ''
    Write-Host 'Ручная настройка (нужен доступ владельца к GitFlic):'
    $i = 1
    foreach ($step in $result.manual_steps) {
        Write-Host ("  {0}. {1}" -f $i, $step)
        $i++
    }
}

if (-not $ok) { exit 1 }
exit 0
