# =============================================================================
# Защита ветки main на GitHub (S21-004): required checks + запрет force-push.
#
# Проблема: GitHub Free для приватного репозитория не даёт branch protection —
# API отвечает 403 «Upgrade to GitHub Pro or make this repository public».
# Скрипт фиксирует точный набор проверок и готов к запуску сразу после смены
# тарифа/видимости; до этого он честно завершается кодом 3 и подсказывает, что
# делать (см. docs/CI.md §10).
#
# Примеры:
#   pwsh scripts/ci/protect-branch.ps1 -DryRun      # показать payload
#   pwsh scripts/ci/protect-branch.ps1 -Verify      # текущее состояние ветки
#   pwsh scripts/ci/protect-branch.ps1              # применить
#
# Требуется gh с правом admin на репозиторий (gh auth status).
# =============================================================================
param(
    [string]$Branch = 'main',
    [string[]]$Checks = @(
        'Lint (backend)',
        'Test (backend)',
        'Frontend',
        'Security',
        'E2E (Playwright)',
        'Docker build'
    ),
    [switch]$DryRun,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'

function Get-Repository {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'gh CLI не найден в PATH'
    }
    $repo = gh repo view --json nameWithOwner --jq .nameWithOwner
    if ($LASTEXITCODE -ne 0 -or -not $repo) {
        throw 'не удалось определить репозиторий (gh auth status / gh repo view)'
    }
    return $repo.Trim()
}

$repo = Get-Repository
Write-Host "==> Репозиторий: $repo, ветка: $Branch"

if ($Verify) {
    gh api "repos/$repo/branches/$Branch/protection" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '==> Защиты ветки нет (или тариф её не поддерживает). Требуемые проверки:'
        foreach ($check in $Checks) { Write-Host "    - $check" }
        exit 1
    }
    exit 0
}

$payload = @{
    required_status_checks        = @{ strict = $true; contexts = $Checks }
    enforce_admins                = $false
    required_pull_request_reviews = @{
        required_approving_review_count = 1
        dismiss_stale_reviews           = $true
    }
    restrictions        = $null
    allow_force_pushes  = $false
    allow_deletions     = $false
} | ConvertTo-Json -Depth 6

if ($DryRun) {
    Write-Host '==> [dry-run] PUT repos/.../branches/'$Branch'/protection'
    Write-Host $payload
    exit 0
}

$payloadFile = Join-Path ([System.IO.Path]::GetTempPath()) "branch-protection-$([guid]::NewGuid()).json"
try {
    Set-Content -LiteralPath $payloadFile -Value $payload -Encoding utf8
    gh api -X PUT "repos/$repo/branches/$Branch/protection" --input $payloadFile
    $code = $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $payloadFile -ErrorAction SilentlyContinue
}

if ($code -ne 0) {
    Write-Host ''
    Write-Host '==> Защита ветки не применена.'
    Write-Host '    GitHub Free + приватный репозиторий: required checks недоступны (403).'
    Write-Host '    Варианты: (1) GitHub Pro; (2) публичный репозиторий;'
    Write-Host '              (3) гейт на GitFlic — docs/CI.md §10, KI-023.'
    exit 3
}

Write-Host "==> Готово: required checks на $Branch — $($Checks -join '; ')"
