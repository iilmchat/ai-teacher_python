# GitFlic setup (S21-002): переменные CI/CD, регистрация агента, запуск конвейера.
#
# Требуется access token GitFlic (Профиль → API токены) со scopes:
#   PROJECT_READ, PROJECT_EDIT, REPOSITORY_READ, REPOSITORY_WRITE, USER_READ,
#   COMPANY_READ (для регистрации агента уровня компании на SaaS).
#
# Пример:
#   $env:GITFLIC_TOKEN = "..."           # токен не передавайте аргументом в shell history
#   pwsh -File scripts/gitflic/setup.ps1 -Company ruchating -RefName sprint/21-ci
#
# Скрипт идемпотентен: существующие переменные не дублируются, повторный запуск
# конвейера создаёт новый (это ожидаемо).
param(
    [string]$Owner = "ruchating",
    [string]$Project = "ai-teacher_python",
    [string]$Company = "",
    [string]$RefName = "sprint/21-ci",
    [switch]$NoPipeline,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Base = "https://api.gitflic.ru"

function Get-Token {
    $t = if ($env:GITFLIC_TOKEN) { $env:GITFLIC_TOKEN } else { $env:GITFLIC_ACCESS_TOKEN }
    if (-not $t) { throw "Не задан GITFLIC_TOKEN (access token GitFlic)" }
    return $t
}

$Token = Get-Token
$Headers = @{ Authorization = "token $Token"; Accept = "application/json" }

function Invoke-GitFlic {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body
    )
    $uri = "$Base$Path"
    $args = @{ Method = $Method; Uri = $uri; Headers = $Headers; TimeoutSec = 30 }
    if ($Body) { $args["Body"] = ($Body | ConvertTo-Json -Depth 6); $args["ContentType"] = "application/json" }
    if ($DryRun) { Write-Host "[dry-run] $Method $uri $($args['Body'])" ; return $null }
    try {
        return Invoke-RestMethod @args
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $text = ""
        try { $text = (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch {}
        throw "GitFlic API $Method $Path -> HTTP $code : $text"
    }
}

Write-Host "==> Проверка токена: GET /user"
$me = Invoke-GitFlic -Method GET -Path "/user"
Write-Host "    пользователь: $($me.username) ($($me.email))"

Write-Host "==> Проект $Owner/$Project"
$proj = Invoke-GitFlic -Method GET -Path "/project/$Owner/$Project"
Write-Host "    default=$($proj.defaultBranch) private=$($proj.private) alias=$($proj.alias)"

# --- 1. CI/CD переменные проекта -------------------------------------------
Write-Host "==> CI/CD переменные проекта"
$existing = @()
try { $existing = @((Invoke-GitFlic -Method GET -Path "/project/$Owner/$Project/setting/cicd/variable").ciCdVariables) } catch { Write-Warning "не удалось прочитать переменные: $_" }
$existingKeys = @($existing | ForEach-Object { $_.key })

$wanted = @(
    @{ key = "SECRET_KEY";        value = "ci_secret_key_do_not_use_in_production"; mask = $true },
    @{ key = "POSTGRES_PASSWORD"; value = "change_me_password";                     mask = $true },
    @{ key = "E2E_PYTHON";        value = "C:\Projects\AI\ai-teacher_python\backend\venv\Scripts\python.exe"; mask = $false }
)

$toAdd = @()
foreach ($v in $wanted) {
    if ($existingKeys -contains $v.key) {
        Write-Host "    [skip] $($v.key) уже есть"
    } else {
        $toAdd += $v
    }
}
if ($toAdd.Count -gt 0) {
    $body = @{ ciCdVariablesToAdd = @($toAdd | ForEach-Object { @{ key = $_.key; value = $_.value; mask = $_.mask } }) }
    $null = Invoke-GitFlic -Method POST -Path "/project/$Owner/$Project/setting/cicd/variable" -Body $body
    Write-Host "    добавлено: $((@($toAdd | ForEach-Object { $_.key })) -join ', ')"
} else {
    Write-Host "    все переменные уже заданы"
}

# --- 2. Регистрация агента (company-level для SaaS) -------------------------
Write-Host "==> Регистрация агента"
$companyAlias = $Company
if (-not $companyAlias) {
    try {
        $companies = Invoke-GitFlic -Method GET -Path "/company/my"
        $list = @($companies._embedded.restCompanyModelList)
        if ($list.Count -gt 0) { $companyAlias = $list[0].alias }
    } catch { Write-Warning "не удалось получить компании: $_" }
}
if ($companyAlias) {
    try {
        $info = Invoke-GitFlic -Method GET -Path "/company/$companyAlias/runners/registration-info"
        Write-Host ""
        Write-Host "    company alias : $companyAlias"
        Write-Host "    registrationUrl  : $($info.registrationUrl)"
        Write-Host "    registrationToken: $($info.registrationToken)"
        Write-Host ""
        Write-Host "    Дальше: установить GitFlic Agent (docs/GITFLIC_RUNNER.md §3-4),"
        Write-Host "    указать tags: docker (Linux/Docker) и/или windows-dev (Windows)."
    } catch {
        Write-Warning "company ${companyAlias}: registration-info недоступен: $_"
    }
} else {
    Write-Warning "Компания не найдена: задайте -Company <alias> (см. GET /company/my)"
}

# --- 3. Запуск конвейера ----------------------------------------------------
if (-not $NoPipeline) {
    Write-Host "==> Запуск конвейера на $RefName"
    $body = @{ refName = $RefName; isTag = "false" }
    $res = Invoke-GitFlic -Method POST -Path "/project/$Owner/$Project/cicd/pipeline/start" -Body $body
    if ($res) { Write-Host "    pipeline_uuid: $($res.pipeline_uuid)" }
    Start-Sleep -Seconds 3
    try {
        $pipelines = Invoke-GitFlic -Method GET -Path "/project/$Owner/$Project/cicd/pipeline?branch=$RefName&size=5"
        $items = @($pipelines._embedded.restPipelineModelList)
        foreach ($p in $items) {
            Write-Host ("    #{0} {1} {2} {3}" -f $p.localId, $p.status, $p.ref, $p.commitId)
        }
    } catch { Write-Warning "не удалось прочитать конвейеры: $_" }
}

Write-Host "==> Готово"
