# GitFlic Runner (агент) — установка и настройка пилота

> Спринт 21 (v0.3.0), S21-002/S21-003. Инструкция для **Windows-машины проекта**
> (`C:\Projects\AI\ai-teacher_python`), на которой уже есть Docker Desktop,
> Node/pnpm и Playwright-браузеры. Настраивает Lead/владелец проекта — учётной
> записи GitFlic у CI-инженера нет, и логиниться он не должен.
>
> **Статус: пилот, не production.** Пайплайн `gitflic-ci.yaml` и эта инструкция
> ещё не проверены на живом GitFlic: первый прогон — это и есть проверка.
> Честные ограничения и known-unknowns — в §10.

---

## 1. Что получится

Пайплайн `.github/workflows/ci.yml` перенесён в `gitflic-ci.yaml` (корень
репозитория). Job'ы распределены по двум агентам, потому что в GitFlic нет
`runs-on`:

| Job | Где выполняется | Образ / сервисы |
|-----|-----------------|-----------------|
| `lint` | Docker-агент, tag `docker` | `python:3.12-slim` |
| `test` | Docker-агент, tag `docker` | `python:3.12-slim` + `services`: `pgvector/pgvector:pg17`, `redis:7-alpine` |
| `frontend` | Docker-агент, tag `docker` | `node:22-alpine` |
| `security-backend` | Docker-агент, tag `docker` | `python:3.12-slim` (pip-audit) |
| `security-frontend` | Docker-агент, tag `docker` | `node:22-alpine` (pnpm audit) |
| `gitleaks` | Docker-агент, tag `docker` | `zricethezav/gitleaks:latest` |
| `e2e` | **PowerShell-агент**, tag `windows-dev` | Windows-хост: Node/pnpm/Playwright, локальные Postgres/Redis |
| `docker` | **PowerShell-агент**, tag `windows-dev` | Windows-хост: Docker Desktop (`docker build`, compose config) |
| `.release` | черновик, закомментирован | Docker-агент + образ gcli |

**Нужны оба агента.** Job'ы с `image`/`services` умеет исполнять только
Docker-агент (PowerShell-агент `image` игнорирует и запускает скрипты прямо на
хосте), а `e2e`/`docker` требуют Windows-хост с Docker Desktop. Если
зарегистрирован только один агент, job'ы второго типа будут висеть в
«ожидании исполнителя», пока не истечёт Maximum job waiting time.

Минимальный порядок пилота: сначала Docker-агент (`lint`/`test` — главное
доказательство работоспособности `services`), затем PowerShell-агент
(`e2e`/`docker`). Пока второго нет, можно временно отключить e2e/docker в
`gitflic-ci.yaml` (перенести вручную в комментарий их `rules`) — но в commit
это состояние не оставлять.

---

## 2. Предварительные требования (эта машина)

| Компонент | Версия | Проверка | Примечание |
|-----------|--------|----------|------------|
| Java (JDK/JRE) | 11+ (≥ 11.0.18) | `java -version` | обязателен для агента; ставит Lead через winget |
| Git | ≥ 2.26 | `git --version` | обязателен для shell/powershell-агента (клон репозитория) |
| Docker Desktop | актуальный | `docker version`, `docker info` | для Docker-агента и для job `docker` |
| Node.js | 22 | `node --version` | для `frontend` (в контейнере) и `e2e` (на хосте) |
| pnpm | 12 | `pnpm --version` | для `e2e` на хосте; в контейнерах ставится corepack'ом |
| Playwright chromium | из `frontend/pnpm-lock.yaml` | `cd frontend; pnpm exec playwright --version` | браузеры должны быть у **пользователя, под которым работает агент** |
| Python | venv проекта (сейчас 3.11.8) | `backend\venv\Scripts\python.exe --version` | нужен e2e через `E2E_PYTHON`, PyPI на хосте заблокирован (KI-017) |
| Агент GitFlic | 1.x, совместимый с SaaS | compatibility table | ставится ниже |

Java 11, если ещё не установлена:

```powershell
winget install --id Microsoft.OpenJDK.11 -e
# либо Eclipse Temurin 11 — главное, чтобы `java -version` был 11+
```

Проверка всего сразу:

```powershell
java -version
git --version
docker version
node --version
pnpm --version
& backend\venv\Scripts\python.exe --version
```

---

## 3. Установка PowerShell-агента (tag `windows-dev`)

Официальная инструкция: <https://docs.gitflic.ru/en/setup/runner/installpowershell/>.
Релизы агента: <https://gitflic.ru/project/gitflic/runner/release/latest>
(таблица совместимости агента и GitFlic — в проекте `gitflic/runner`).

> Для версий агента **1.7.1 и ниже** выбор рабочего каталога недоступен,
> используется `%USERPROFILE%\gitflic-runner`. Параметры `runner.workingDir` /
> `runner.helperDir` появились в 2.0.x — если ставится 2.0+, их можно указать
> в `config/application.properties`.

### 3.1. Рабочий каталог

Создаём каталог и подкаталоги **от имени пользователя, который будет запускать
агента** (для e2e/docker это должен быть интерактивный пользователь машины,
см. §3.5):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner\build"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner\cache"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner\data\log"
```

### 3.2. Файлы агента

Из скачанного архива релиза (распаковать во временный каталог) скопировать:

```powershell
Copy-Item .\runner.jar, .\helper.jar "$env:USERPROFILE\gitflic-runner"
Copy-Item .\scripts\helper.bat "$env:USERPROFILE\gitflic-runner"
```

- `runner.jar` — сам агент;
- `helper.jar` — служебные операции до/после задачи (артефакты, кэш);
- `helper.bat` — batch-обёртка, через которую агент вызывает helper.jar.

Без `helper.jar` + `helper.bat` агент не сможет корректно выполнять CI/CD-задачи
(официальная документация).

### 3.3. Регистрация агента в GitFlic

Регистрация на облачном `gitflic.ru` — **только на уровне компании**, не
проекта:

1. GitFlic → нужная компания → **Settings → CI/CD Agents**
   (`https://gitflic.ru/company/<company_alias>/setting/cicd/runners`).
2. Нажать создание агента, **скопировать URL и Token** (токен показывается
   один раз).
3. В каталоге агента выполнить:

```powershell
Set-Location "$env:USERPROFILE\gitflic-runner"
java -jar runner.jar register `
  --url "<URL из UI>" `
  --registration-token "<Token из UI>" `
  --name "ai-teacher-windows-dev" `
  --tags "windows-dev"
```

После успешной регистрации в UI появится подключённый агент, а в каталоге —
`config\application.properties`.

4. Теги можно задать и позже в UI агента (поле **Tags**). Важно: агент берёт
   задачи только с теми тегами, что указаны у него; наш e2e/docker ждут
   `windows-dev`. Опцию **Run untagged jobs** включённой не держать — все наши
   job'ы тегированы явно.

### 3.4. `config/application.properties`

Минимум для PowerShell-агента:

```properties
# Тип агента: скрипты выполняются напрямую в PowerShell на хосте
runner.executor=powershell

# Лог: путь относительно каталога агента
logging.file.name=data/log/server.log
logging.level.root=INFO

# Рабочий каталог (2.0.x+; в 1.x — %USERPROFILE%\gitflic-runner по умолчанию)
# runner.workingDir=C:/Users/<user>/gitflic-runner
# runner.helperDir=C:/Users/<user>/gitflic-runner

# Ограничение размера переменных задачи (по умолчанию 262144 символа)
# runner.job-variables-size-limit-characters=262144
```

- **Конкурентность.** `runner.runnerConcurrencyMode` (AUTO/DEFAULT/CUSTOM)
  документирован только для агентов типа docker и kuber; PowerShell-агент
  выполняет задачи последовательно. Значит `e2e` и `docker` на одном агенте
  пойдут друг за другом — это нормально для пилота.
- **Один контекст выполнения.** `runner.enableExecScriptsInSession=true`
  (default) — все скрипты задачи в одном контексте; наши PowerShell-скрипты
  самодостаточны и не полагаются на это.
- **Кодировка.** Если русский текст в логах превращается в «кракозябры», см.
  §9 (locale/encoding) — документация GitFlic рекомендует
  `logging.charset.console=windows-1251` и настройку профиля PowerShell.
- После правки `application.properties` агент перезапустить.

### 3.5. Запуск

**Пилот: foreground** (проще всего проверить захват задач и увидеть ошибки):

```powershell
Set-Location "$env:USERPROFILE\gitflic-runner"
java -jar runner.jar start --config=config/application.properties
```

**Как задачу планировщика (после проверки foreground).** Для e2e/docker агент
должен работать в сессии пользователя, у которого есть Docker Desktop и
Playwright-браузеры, поэтому — триггер «при входе в систему», а не служба
LocalSystem:

```powershell
$runnerDir = "$env:USERPROFILE\gitflic-runner"
$action = New-ScheduledTaskAction -Execute "java.exe" `
  -Argument "-jar runner.jar start --config=config/application.properties" `
  -WorkingDirectory $runnerDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
  -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName "GitFlic Runner (windows-dev)" `
  -Action $action -Trigger $trigger -Settings $settings `
  -Description "GitFlic PowerShell agent: e2e/docker" -Force
Start-ScheduledTask -TaskName "GitFlic Runner (windows-dev)"
```

Проверить: `Get-ScheduledTask -TaskName "GitFlic Runner (windows-dev)"`,
лог — `%USERPROFILE%\gitflic-runner\data\log\server.log`.

> **Служба Windows (NSSM/WinSW) для `windows-dev` не рекомендуется:** служба
> стартует вне пользовательской сессии, из-за чего типично ломаются доступ к
> Docker Desktop (npipe) и Playwright-браузеры в профиле пользователя.
> Служба допустима для Docker-агента (ему GUI не нужен), но и там npipe —
> см. §4.5.

### 3.6. Безопасность агента

- Отдельный пользователь/профиль (рекомендация документации) — но для
  Windows-хоста с e2e это должен быть пользователь, в сессии которого доступны
  Docker Desktop и браузеры; компромисс: выделенная учётка + `docker-users` +
  установка Playwright под неё.
- В `config/application.properties` лежит **токен агента** (`runner.registrationToken`)
  и его id. Ограничить ACL каталога (`icacls`), не коммитить, не пересылать в
  чатах; при компрометации — удалить агента в UI и зарегистрировать заново.
- Агент = удалённое выполнение кода на хосте. Не давать лишних прав (админ не
  нужен; для Docker достаточно группы `docker-users`), держать машину
  обновлённой, не открывать порты агента наружу.
- В GitFlic маскируются значения переменных, но job-скрипты к ним доступ
  имеют. Не запускать пайплайны из недоверенных форков/веток с секретами;
  секреты — только в CI/CD проекта (не в YAML).

---

## 4. Альтернатива: Docker-агент (для `image`/`services`)

Docker-агент нужен в любом случае: `lint`/`test`/`frontend`/`security`/
`gitleaks` используют `image` и `services`. На этой машине он может работать
через Docker Desktop (Linux-контейнеры) и `npipe`.

Официальные инструкции:
<https://docs.gitflic.ru/en/setup/runner/installdocker/>,
<https://docs.gitflic.ru/en/setup/runner/volumes/>,
<https://docs.gitflic.ru/en/setup/runner/app_prop/>.

### 4.1. Рабочий каталог и файлы

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner-docker"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner-docker\build"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner-docker\cache"
New-Item -ItemType Directory -Force "$env:USERPROFILE\gitflic-runner-docker\data\log"
Copy-Item .\runner.jar, .\helper.jar "$env:USERPROFILE\gitflic-runner-docker"
```

Для Docker-агента `helper.bat`/`helper.sh` не нужен (helper запускается в
контейнере), но `helper.jar` нужен.

### 4.2. Регистрация

```powershell
Set-Location "$env:USERPROFILE\gitflic-runner-docker"
java -jar runner.jar register `
  --url "<URL из UI>" `
  --registration-token "<Token из UI>" `
  --name "ai-teacher-docker" `
  --tags "docker"
```

### 4.3. `config/application.properties`

Windows-хост с Docker Desktop:

```properties
runner.executor=docker

# Docker Desktop на Windows: именованный канал, не unix-socket
docker.host=npipe:////./pipe/docker_engine

# DinD-режим самого агента не включаем: контейнеры запускаются через хостовый
# Docker Desktop. didEnable=true вместе с docker:dind в job'е документация
# называет источником некорректного поведения.
docker.didEnable=false

# privileged=true нужен ТОЛЬКО если в job'ах будет сервис docker:dind
# (наш docker job его не использует — он на PowerShell-агенте).
docker.privileged=false

# Сеть контейнеров: host удобен на одной машине; bridge — если нужна изоляция
docker.networkMode=host

# Зеркало/реестр: из-за лимитов Docker Hub документация GitFlic рекомендует
# их реестр. Логин/пароль — gitflic.ru username и transport token.
docker.registry-url=https://registry.gitflic.ru
docker.registry-username=<gitflic username>
docker.registry-password=<transport token>

logging.file.name=data/log/server.log
logging.level.root=INFO
```

- **Тома.** Если job'ам нужны host-каталоги, монтирование задаётся как у
  `docker -v`:
  `docker.volumes[0]=<host-path>:<container-path>` (bind/named/anonymous
  volumes; драйвер — `docker.volume-driver`, кэш анонимных томов —
  `docker.cache_dir`). Для нашего пайплайна дополнительные тома не нужны:
  клон и кэш агент держит сам.
- **Helper-образ.** Если Docker Hub недоступен/лимитирует, задать
  `runner.helperImage=registry.gitflic.ru/company/gitflic/gitflic-runner-helper:<версия агента>`
  и авторизацию в `registry.gitflic.ru` (см. документацию).
- **Рабочий каталог** (`runner.workingDir`, 2.0.x+) можно указать явно:
  `runner.workingDir=C:/Users/<user>/gitflic-runner-docker`.

### 4.4. Запуск

```powershell
Set-Location "$env:USERPROFILE\gitflic-runner-docker"
java -jar runner.jar start --config=config/application.properties
```

Для Docker-агента служба допустима, но на этой машине мешает та же проблема,
что и у PowerShell-агента: **Docker Desktop должен быть запущен, а npipe —
доступен пользователю агента**. Если служба не видит `docker info` — запускать
в сессии пользователя (Task Scheduler «At logon»), как в §3.5.

### 4.5. Docker Desktop из-под сервисного аккаунта

Симптом: агент в службе, job'ы падают на «Cannot connect to the Docker daemon
at npipe:////./pipe/docker_engine» или `docker info` возвращает ошибку.

Причины и лечение:

- Docker Desktop запущен не у того пользователя / не запущен вообще — запустить
  Docker Desktop в сессии пользователя агента;
- пользователь агента не в группе `docker-users`:
  `net localgroup docker-users <user> /add` (нужна перелогин-сессия);
- служба работает как `LocalSystem` и не имеет доступа к пользовательскому
  npipe — перейти на Task Scheduler «At logon» от нужного пользователя;
- Docker Desktop в режиме «Windows containers» — переключить на Linux
  containers (образы `python:3.12-slim` и т.п. — Linux).

---

## 5. Настройка проекта GitFlic

1. **Импорт репозитория** (Lead): GitHub PAT → GitFlic «Импорт проекта»
   (подробно — [CI.md §6](CI.md), в т.ч. отзыв PAT после импорта).
2. **CI/CD → Configuration File Path**: `gitflic-ci.yaml` (файл в корне).
3. **CI/CD → Enable Merge Request Pipeline**: включить — это основной гейт для
   MR. Флажок **Merge Result Pipeline** — отдельный; по документации GitFlic
   это Enterprise-функция, на Free может быть недоступна (в `workflow:rules`
   она учтена, но не обязательна).
4. **Task Restart Timeout**: поставить с запасом, например `1800`–`2400` секунд
   (в YAML отдельного `timeout`-ключа нет). Это же значение ограничивает
   «зависшие» job'ы.
5. **Auto-cancel outdated pipelines** — включить (не запускать устаревшие
   пайплайны ветки).
6. **Агенты**: зарегистрировать оба (Docker `docker`, PowerShell `windows-dev`),
   проверить статус Active и что теги видны в UI агента. «Run untagged jobs»
   выключить.
7. **Переменные CI/CD** (CI/CD → Task Variables / Variables). Значения
   секретов — с галочкой **Mask**:

   | Имя | Значение | Mask | Зачем |
   |-----|----------|------|-------|
   | `SECRET_KEY` | случайная строка ≥ 32 символов | **да** | JWT в тестах и e2e |
   | `POSTGRES_PASSWORD` | пароль локального compose-Postgres (из `.env`) | **да** | `test` (сервис+job) и `e2e` (локальная БД) |
   | `E2E_PYTHON` | `C:\Projects\AI\ai-teacher_python\backend\venv\Scripts\python.exe` | нет | e2e: backend-интерпретатор с зависимостями (PyPI на хосте заблокирован) |
   | `E2E_POSTGRES_PORT` | `5434` | нет | опционально: порт локального Postgres (KI-001) |
   | `E2E_REDIS_PORT` | `6381` | нет | опционально: порт локального Redis |
   | `E2E_POSTGRES_USER` | `ai_teacher` | нет | опционально, если отличается в `.env` |
   | `E2E_POSTGRES_DB` | `ai_teacher` | нет | опционально, если отличается в `.env` |

   **Не создавайте** переменные проекта `POSTGRES_HOST` / `POSTGRES_PORT` /
   `POSTGRES_USER` / `POSTGRES_DB` / `REDIS_HOST` / `REDIS_PORT`: по документации
   GitFlic переменные проекта перекрывают `variables` из YAML, и job `test`
   получит адреса e2e вместо сервисов `postgres`/`redis`. Job `test` уже
   принудительно выставляет `POSTGRES_HOST/PORT`, `REDIS_HOST/PORT`, но
   `USER/DB` не переопределяет намеренно; для e2e используйте префикс `E2E_*`.

8. **Первый прогон**: создать пайплайн вручную на ветке `sprint/21-ci`
   (CI/CD → Pipelines → Create Pipeline) — `workflow:rules` разрешает
   branch-пайплайны для `sprint/**` на время пилота. Смотреть, какие job'ы
   захвачены агентами, и разбирать ошибки по §9.

---

## 6. Ожидаемые тайминги (ориентир, одна машина)

| Job | Холодный прогон | С кэшем/прогретый | Примечание |
|-----|-----------------|--------------------|------------|
| `lint` | 1.5–2.5 мин | 1–1.5 мин | pip + ruff/mypy |
| `test` | 6–9 мин | 5–7 мин | pip (~1–2 мин), pytest ~200 с, миграции |
| `frontend` | 2.5–4 мин | 1.5–2.5 мин | pnpm install + typecheck/lint/vitest/build |
| `security-backend` | 1–2 мин | 1–2 мин | pip-audit ходит в PyPI/OSV |
| `security-frontend` | 0.5–1 мин | 0.5–1 мин | lockfile-аудит |
| `gitleaks` | 0.5–1 мин | 0.5–1 мин | зависит от глубины истории |
| `e2e` | 2–3 мин | 2–3 мин | pnpm install + Playwright ~1.2 мин + webServer |
| `docker` | 3–5 мин | 2–4 мин | сборка backend/frontend (Docker layer cache) |

Параллельность: `lint`, `frontend` и три `security`-job'а стартуют одновременно
(`frontend`/`security` с `needs: []`), `test` — после `lint`, `e2e` и `docker` —
после `lint` + `test`. На Docker-агенте задача одна, так что `lint`/`test`/
`frontend`/`security` фактически идут последовательно; целевой ориентир из
[CI.md §5](CI.md) — PR-пайплайн ≤ 10 минут с кэшем. PowerShell-агент выполняет
`e2e` и `docker` последовательно, итог может выйти за 10 минут — это ожидаемый
минус одномашинного пилота.

---

## 7. Переменные и окружение: что где задаётся

- `gitflic-ci.yaml` — только несекретные дефолты (`test_pass`, dummy
  `SECRET_KEY`, адреса сервисов). Секреты — в CI/CD проекта.
- Docker-agent job'ы: `POSTGRES_PASSWORD`/`SECRET_KEY` приходят из CI/CD и
  перекрывают YAML. Пароль сервиса и пароль клиента должны совпадать — они
  берутся из одного источника (переменная проекта), поэтому сходятся.
- `e2e`: `E2E_PYTHON` обязателен; `POSTGRES_PASSWORD` и `SECRET_KEY`
  наследуются из CI/CD (если `SECRET_KEY` нет — подставляется demo-значение).
  Локальные порты/пользователь/БД — дефолты из `gitflic-ci.yaml` (5434/6381,
  `ai_teacher`), переопределяются `E2E_*`-переменными.
- `docker` (job): `POSTGRES_PASSWORD`/`SECRET_KEY` нужны только для проверки
  `docker-compose.prod.yml` (там `:?`); если не заданы — берутся заглушки,
  ничего не деплоится.

---

## 8. Разрешения и артефакты

- **Артефакт e2e**: `frontend/playwright-report`, хранится 7 дней, создаётся
  всегда (`when: always`) — смотреть при падении. Трассы/скриншоты Playwright
  пишет в `frontend/test-results` (в артефакты не включены; при необходимости
  добавить путь в `artifacts.paths` job'а `e2e`).
- **Coverage XML** создаётся в `backend/coverage.xml` (job `test`), но в
  артефакты не выкладывается — в GitHub он уходил в codecov, в GitFlic
  аналога нет. При необходимости — добавить `artifacts` или публиковать через
  API.
- **Кэш** — локальный на агенте, сбрасывается вручную в UI (нужны права
  Administrator+). Кэш не общий между Docker- и PowerShell-агентами; у
  PowerShell-агента кэш в наших job'ах не используется (механизм кэша в
  документации описан для Docker-агента). Первый прогон всегда холодный.

---

## 9. Troubleshooting

### 9.1. Job висит «в ожидании исполнителя» / pipeline не создаётся

| Симптом | Причина | Решение |
|---------|---------|---------|
| Job в статусе ожидания, агент online | тег job'а не совпадает с тегами агента | сверить `tags` в YAML (`docker`, `windows-dev`) с тегами в UI агента; теги задаются при регистрации (`--tags`) и в настройках агента |
| Job висит, агент «не забирает» | агент не Active / offline; «Run untagged jobs» выключен, а job без тега | включить агента; проверить, что у всех job'ов есть тег; дождаться Maximum job waiting time |
| Job `test`/`frontend` ждёт, хотя Docker-агент есть | `image` может исполнять только агент типа docker; PowerShell-агент такие job'ы не берёт | зарегистрировать Docker-агент (§4) |
| Pipeline не создался на push | ветка не `main`/`sprint/**` и не MR; MR-пайплайн выключен; `workflow:rules` отсекает | включить Enable Merge Request Pipeline; создать пайплайн вручную из UI; проверить `CI_PIPELINE_TYPE` |
| Нет job'ов `e2e`/`docker` в MR | сработал docs-only фильтр `rules:changes` | ожидаемо, если изменены только docs/README/*.md |

### 9.2. `test`: Postgres/Redis

| Симптом | Причина | Решение |
|---------|---------|---------|
| `PostgreSQL host:port не открылся за 60 с` | сервис не стартовал / не тот alias | смотреть лог job'а и сервисов; проверить `services.name`/`alias`; **проверить, что env job'а (POSTGRES_*) доходят до контейнера сервиса** — в документации GitFlic env для `services` не описан; это ключевая неизвестность пилота |
| `PostgreSQL открыт, но вход не удался` | сервис поднялся с другим паролем/пользователем | убедиться, что `POSTGRES_PASSWORD` из CI/CD одинаково виден сервису и job'у; временно убрать переменную проекта и проверить с `test_pass` |
| `extension "vector" is not available` | образ без pgvector | используется `pgvector/pgvector:pg17` (KI-003) — не менять на `postgres:*` |
| `Redis ... недоступен` | сервис redis не стартовал | проверить `redis:7-alpine`, alias `redis`; тесты rate-limit в основном не ходят в Redis (`RATE_LIMIT_ENABLED=false`) |

> Если окажется, что GitFlic не прокидывает переменные job'а в сервисные
> контейнеры, `test` в текущем виде не заработает — это блокер пилота. Варианты:
> обратиться в поддержку GitFlic, либо временно перейти на внешний Postgres
> (переменные `POSTGRES_HOST` и т.п. в job'е указывают на существующий сервер),
> либо вернуться к GitHub/self-hosted runner (см. критерии в CI.md §5).

### 9.3. Docker-agent job'ы

| Симптом | Решение |
|---------|---------|
| `Cannot connect to the Docker daemon` / `docker info` падает | Docker Desktop не запущен или npipe недоступен пользователю агента — §4.5 |
| `pull access denied` / rate limit Docker Hub | настроить `docker.registry-*` на `registry.gitflic.ru` и `runner.helperImage`; либо залогиниться в Docker Hub на хосте |
| Контейнер job'а не стартует: `exec format error` / CRLF | клон на Windows получил CRLF-файлы, а Linux-контейнер ждёт LF: у пользователя агента `git config --global core.autocrlf false` и переклонировать рабочую директорию |
| Долгий «холодный» запуск | пустой кэш pip/pnpm; второй прогон быстрее; проверить `cache.paths`/`key` |

### 9.4. `e2e` на PowerShell-агенте

| Симптом | Решение |
|---------|---------|
| `E2E_PYTHON не задан` | добавить переменную проекта `E2E_PYTHON` (§5) — в клоне агента venv нет |
| `E2E_PYTHON указывает на несуществующий файл` | путь должен существовать на машине агента; venv не переносится между пользователями/машинами |
| `Executable doesn't exist ... playwright` | браузеры не установлены у пользователя агента: `cd frontend; pnpm exec playwright install chromium` (или задать `PLAYWRIGHT_BROWSERS_PATH` на общий каталог) |
| `EADDRINUSE :8001/:3100` | `CI=true` отключает `reuseExistingServer`; закрыть зависшие uvicorn/vite с прошлого прогона или перезапустить агента/машину |
| `password authentication failed for user "ai_teacher"` | `POSTGRES_PASSWORD` не совпадает с паролем локального compose-кластера; сверить `.env` |
| `database "ai_teacher_e2e" does not exist` / нет прав создать БД | `prepare_e2e_db.py` создаёт БД; пользователь Postgres должен иметь CREATEDB (в dev-compose `POSTGRES_USER` — суперпользователь); проверить, что локальные `docker compose up -d postgres redis` подняты |
| Таймаут webServer (120 с) | backend долго стартует: проверить `alembic`/`uvicorn` в логе, свободен ли 8001, доступен ли venv-python |
| Русский текст в логе нечитаем | encoding: `logging.charset.console=windows-1251` в `application.properties`; профиль PowerShell — `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` (или windows-1251, как советует документация); `Set-ExecutionPolicy RemoteSigned` |

### 9.5. `e2e`/`docker`: Docker Desktop из-под агента

См. §4.5. Коротко: агент должен работать в сессии пользователя с запущенным
Docker Desktop; пользователь — в группе `docker-users`; для проверки
`docker info` — тот же пользователь/сессия.

### 9.6. Прочее

| Симптом | Причина/решение |
|---------|-----------------|
| `runner.executor is not declared...` при старте агента | в `config/application.properties` нет строки `runner.executor=powershell` (или `docker`) — добавить |
| Регистрация: `PKIX path building failed` | самоподписанный сертификат GitFlic — настроить trust для агента (документация «Self-Signed Certificate Agent Setup») |
| В логах `***`/`[MASKED]` вместо значения | это маскировка секрета GitFlic — нормально; проверить, что реальное значение не утекло |
| gitleaks находит «утечку» в новом файле | добавить не-секрет в `.gitleaks.toml` allowlist (как `test_pass`, `ci_secret_key_do_not_use_in_production`), не отключать правила |
| `ERR_PNPM_IGNORED_BUILDS` | pnpm 12: `--allow-build=esbuild` и `frontend/pnpm-workspace.yaml` (`onlyBuiltDependencies`), RULES §11.10 |
| `corepack prepare pnpm@12` падает | нет сети до registry.npmjs.org у агента; проверить прокси/доступ; альтернатива — `npm i -g pnpm@12` на хосте (для e2e) |

---

## 10. Честные ограничения пилота

- **Cloud-агенты GitFlic по умолчанию выключены** — всегда работаем своим
  агентом. Машина должна быть включена и онлайн, иначе CI не идёт; это
  single point of failure.
- **Нужны два агента** (Docker + PowerShell на этой машине). Пока второго нет,
  `e2e`/`docker` не выполняются; пока нет Docker-агента — не выполняются
  `lint`/`test`/`frontend`/`security`.
- **Зеркало GitHub↔GitFlic в облаке** создаётся по запросу в поддержку и
  обновляется раз в сутки — не рассчитывать на near-real-time синхронизацию.
- **Встроенный Gitleaks** есть только в self-hosted GitFlic; на SaaS — обычный
  job с образом gitleaks (как у нас). SAST/DAST/merge trains/аудит — платные
  тарифы, мы их не используем.
- **Merge Result Pipeline** — Enterprise-функция; на Free доступен MR-пайплайн.
  Поведение «красный конвейер блокирует merge» проверяется отдельно (S21-004).
- **`services` без env/healthcheck** — главная непроверенная гипотеза:
  переменные job'а могут не доходить до Postgres/Redis. Если не доходят —
  `test` в текущем виде блокирован (см. §9.2).
- **PowerShell-агент и Docker Desktop** — доступ к npipe из службы не
  гарантирован; пилот опирается на запуск в пользовательской сессии.
- **E2E зависит от dev-машины**: `E2E_PYTHON` указывает на
  `backend\venv` рабочего checkout'а (PyPI на хосте заблокирован, KI-017), а
  тесты используют локальные Postgres/Redis из docker compose. Это pilot-hack:
  при переезде на выделенный runner понадобится либо доступный PyPI, либо
  предустановленный venv/образ.
- **Ничего не проверено на живом GitFlic**: YAML провалидирован локально
  (`yaml.safe_load`), shell-блоки — `sh -n`, PowerShell-блоки — парсером
  PowerShell; но реальные имена сервисов/alias, env сервисов, кэш, теги и
  тайминги подтверждаются только первым прогоном.
- **KI-014** закрывается только после зелёного пайплайна на выбранной
  платформе и проверки required checks — этот runbook готовит инфраструктуру,
  а не объявляет CI восстановленным.

---

## 11. Ссылки

- Справочник `gitflic-ci.yaml`: <https://docs.gitflic.ru/en/cicd/gitflic-ci-yaml/>
- Пайплайны и MR-пайплайн: <https://docs.gitflic.ru/en/cicd/pipeline/>
- Настройки CI/CD проекта: <https://docs.gitflic.ru/en/cicd/cicd-settings/>
- Кэш: <https://docs.gitflic.ru/en/cicd/cache/>
- Типы агентов: <https://docs.gitflic.ru/en/setup/runner/agent_types/>
- Установка PowerShell-агента: <https://docs.gitflic.ru/en/setup/runner/installpowershell/>
- Установка Docker-агента: <https://docs.gitflic.ru/en/setup/runner/installdocker/>
- Параметры `application.properties`: <https://docs.gitflic.ru/en/setup/runner/app_prop/>
- Тома Docker-агента: <https://docs.gitflic.ru/en/setup/runner/volumes/>
- Troubleshooting агента: <https://docs.gitflic.ru/en/faq/faq_runner/>
- Сборки агента: <https://gitflic.ru/project/gitflic/runner/release/latest>
- Наш план и критерии пилота: [CI.md](CI.md) · [TODO_V0.3.md](../TODO_V0.3.md) (S21-002/S21-003)
