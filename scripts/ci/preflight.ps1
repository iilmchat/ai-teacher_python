# Preflight self-hosted runner (S37-001).
#
# Быстро (десятки секунд) проверяет, что раннер пригоден для job'а: Docker
# daemon отвечает, есть место на диске, workspace записываемый, на месте
# ключевые скрипты. Если что-то не так — job падает красным сразу, а не
# зависает на середине.
#
# Ограничение платформы: если раннер полностью offline, GitHub не запускает
# job вообще (статус queued) — этот скрипт внутри job'а помочь не может.
# Для такого случая см. docs/CI.md §10 (branch protection/required checks) и
# GitFlic merge-gate.

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Host "PREFLIGHT FAILED: $Message" -ForegroundColor Red
    exit 1
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$runner = if ($env:RUNNER_NAME) { $env:RUNNER_NAME } else { $env:COMPUTERNAME }
Write-Host "==> preflight: runner=$runner host=$env:COMPUTERNAME cwd=$((Get-Location).Path)"

# 1. Docker CLI + daemon (все тяжёлые job'ы используют Docker).
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail 'docker CLI не найден в PATH (Docker Desktop не установлен?)'
}
$dockerJob = Start-Job -ScriptBlock {
    $version = docker info --format '{{.ServerVersion}}' 2>&1
    if ($LASTEXITCODE -ne 0) { "ERROR: $version" } else { "$version" }
}
if (-not (Wait-Job $dockerJob -Timeout 25)) {
    Stop-Job $dockerJob -ErrorAction SilentlyContinue
    Remove-Job $dockerJob -Force -ErrorAction SilentlyContinue
    Fail 'Docker daemon не ответил за 25 с (Docker Desktop запущен?)'
}
$dockerOut = (Receive-Job $dockerJob | Out-String).Trim()
$dockerOk = $dockerJob.State -eq 'Completed'
Remove-Job $dockerJob -Force -ErrorAction SilentlyContinue
if (-not $dockerOk -or $dockerOut -notmatch '^\d+\.\d+') {
    Fail "Docker daemon недоступен: $dockerOut"
}
Write-Host "    docker: $dockerOut"

# 2. Свободное место (по умолчанию минимум 2 ГБ).
$minFreeGb = 2.0
if ($env:CI_MIN_FREE_GB) { $minFreeGb = [double]$env:CI_MIN_FREE_GB }
$current = (Resolve-Path (Get-Location)).Path
$driveName = (Get-Item $current).PSDrive.Name
$drive = Get-PSDrive -Name $driveName
$freeGb = [math]::Round($drive.Free / 1GB, 1)
if ($freeGb -lt $minFreeGb) {
    Fail "мало места на $($driveName): $freeGb ГБ < $minFreeGb ГБ"
}
Write-Host "    disk: $freeGb ГБ свободно"

# 3. Workspace записываемый.
$probe = Join-Path (Get-Location) ".preflight-$PID.tmp"
try {
    Set-Content -Path $probe -Value 'ok' -Encoding ascii
    Remove-Item $probe -Force
} catch {
    Fail "workspace не записывается: $($_.Exception.Message)"
}

# 4. Ключевые файлы/скрипты на месте (защита от неполного checkout).
$required = @(
    'scripts/ci/backend-lint.sh',
    'scripts/ci/backend-test.sh',
    'scripts/ci/frontend.sh',
    'scripts/ci/security-backend.sh',
    'gitflic-ci.yaml',
    'backend/requirements.txt'
)
foreach ($item in $required) {
    if (-not (Test-Path -LiteralPath $item)) {
        Fail "нет обязательного файла: $item"
    }
}

$sw.Stop()
Write-Host "==> preflight OK ($([math]::Round($sw.Elapsed.TotalSeconds, 1)) с)"
