# Подготовка проекта к запуску на GitFlic: CI/CD и сборка

Практическое руководство по переводу проекта, аналогичного `ai-teacher_python`,
с GitHub (или GitLab) на GitFlic — вместе со сборкой, тестами и гейтами на мерж.

| Параметр | Значение |
|---|---|
| Версия документа | 1.0 |
| Дата | 2026-11-04 |
| Референс | `ai-teacher_python` v0.3.2: Python 3.12 + FastAPI, React 19 + Vite, PostgreSQL 17 + pgvector, Redis, Docker Compose |
| Аудитория | Техлид/DevOps проекта, который переезжает на GitFlic |
| Статус | Конфиги и команды проверены локально в тех же Docker-образах, что и в CI. Живой прогон на SaaS-контуре — по чек-листу §10 |
| Что внутри | Порядок действий, готовые конфиги, грабли, критерии приёмки, чек-лист передачи |

---

## 0. Коротко

GitFlic — это Git-хостинг с CI/CD, синтаксис которого близок к GitLab CI, но
есть важные отличия: **нет `runs-on` и `uses`**, задачи разбираются по **тегам
агентов**, а `image`/`services` умеет исполнять только агент типа **docker**.
Сборка и проверки остаются обычными shell-командами в контейнере или на хосте.

Минимальный путь:

1. Импортировать репозиторий, проверить ветки/теги, настроить LF/CRLF.
2. Разложить проверки: «дешёвые» — в Docker-агент, «требующие Windows/GUI» — в
   PowerShell-агент.
3. Написать `gitflic-ci.yaml`: стадии, правила запуска, кэш, сервисы.
4. Поднять агентов и выдать им теги.
5. Завести переменные/секреты в CI/CD проекта (не в YAML).
6. Собрать образы, проверить compose, при желании — пушить в registry GitFlic.
7. Включить MR-пайплайн, защиту ветки и проверку статуса конвейера при слиянии.
8. Прогнать пилот (`lint` + `test`), затем полный пайплайн и приёмку.

**Оценка трудозатрат:** пилот на одном Docker-агенте — 1–2 рабочих дня;
полный пайплайн с e2e, сборкой и гейтами — ещё 2–3 дня. Стоимость на Free-тарифе
— 0 ₽, но нужна своя всегда включённая машина под агента.

**Два правила, которые экономят больше всего времени:**

- не тащить в YAML синтаксис GitHub/GitLab, который не описан в документации
  GitFlic (неизвестный ключ ломает разбор конфига — см. §5.3);
- секреты и адреса сервисов держать в переменных проекта, а не в файле, но
  помнить: **переменные проекта перекрывают `variables` из YAML** (§7).

---

## 1. Что должно получиться

```text
   push / merge request / tag
              │
              ▼
   ┌──────────────────────────────────────────────┐
   │  GitFlic (SaaS)  ── очередь задач ──►  агенты │
   └───────┬──────────────────────────────┬────────┘
           │ tag: docker                  │ tag: windows-dev
           ▼                              ▼
   Docker-агент                      PowerShell-агент
   (Linux-контейнеры)                (Windows-хост)
   lint, test, frontend,             e2e (Playwright),
   security, gitleaks, release       docker build, compose
```

| Job | Что проверяет | Агент (tag) | Образ / сервисы |
|---|---|---|---|
| `lint` | ruff + mypy (strict) | `docker` | `python:3.12-slim` |
| `test` | alembic + pytest на реальной БД | `docker` | `python:3.12-slim` + `pgvector/pgvector:pg17`, `redis:7-alpine` |
| `frontend` | typecheck, lint, unit, build | `docker` | `node:22-alpine` |
| `security-backend` | `pip-audit` | `docker` | `python:3.12-slim` |
| `security-frontend` | `pnpm audit --audit-level=high` | `docker` | `node:22-alpine` |
| `gitleaks` | поиск секретов в истории | `docker` | `zricethezav/gitleaks` |
| `e2e` | Playwright на живом стенде | `windows-dev` | хост: Node, pnpm, браузеры, Postgres/Redis |
| `docker` | сборка образов + валидация compose | `windows-dev` | Docker Desktop хоста |
| `release` | заметки релиза на теге | `docker` | `python:3.12-slim` |

Почему два агента, а не один: job'ы с `image` и `services` выполняет только
агент типа docker; e2e и сборке через Docker Desktop нужен Windows-хост с
запущенным Docker Desktop в сессии пользователя. Если зарегистрирован один
агент, задачи второго типа висят «в ожидании исполнителя», пока не истечёт
таймаут ожидания, — и конвейер выглядит красным без причины.

**Практический приём:** на время пилота держите два конфига — минимальный
(`ci/gitflic-pilot.yaml`: только `lint` и `test`) и полный (`gitflic-ci.yaml`).
Путь к конфигу переключается в настройках CI/CD проекта, поэтому первый живой
прогон не зависит от второго агента.

---

## 2. Что подготовить заранее

| Что | Требование | Как проверить |
|---|---|---|
| Аккаунт GitFlic и компания | Free: приватные репозитории до 5 человек, 4 ГБ на репозиторий, CI/CD включён | `gitflic.ru/price` |
| Репозиторий-источник | Доступ на чтение; для приватного GitHub — PAT | `git ls-remote <url>` |
| Машина под агента | Windows 10/11 или Linux, всегда включена, стабильная сеть | — |
| Java | 11+ (нужна самому агенту) | `java -version` |
| Git | ≥ 2.26 | `git --version` |
| Docker | Docker Desktop (Linux-контейнеры) или Docker Engine | `docker info` |
| Node.js / pnpm | Node 22, pnpm 12 (для frontend и e2e) | `node --version`, `pnpm --version` |
| Python | venv проекта (для e2e на хосте, если PyPI недоступен) | `python --version` |
| Права | Пользователь агента в группе `docker-users`; доступ к npipe | `docker info` от этого пользователя |
| Время | 1–2 дня на пилот, 3–5 дней на паритет | — |

Для e2e на Windows-хосте браузеры Playwright должны быть установлены **у того
пользователя, под которым работает агент** (`pnpm exec playwright install
chromium`).

---

## 3. Шаг 1. Репозиторий

### 3.1. Импорт

1. Для приватного источника выпустить PAT с минимальными правами:
   fine-grained → только нужный репозиторий, `Contents: Read-only`, срок 7–30 дней.
2. GitFlic → «+» → **Импорт проекта**: URL, логин, токен.
3. Проверить: default-ветка, теги, история коммитов, что `.github/` не мешает
   (он просто лежит, workflow'ы GitHub не исполняются).
4. **Отозвать PAT** сразу после импорта.

Зеркалирование GitHub ↔ GitFlic в облаке создаётся по запросу в поддержку и
обновляется примерно раз в сутки — как механизм синхронизации «здесь и сейчас»
не годится. Либо переезд origin, либо зеркало как архив.

### 3.2. Гигиена репозитория (делается до первого прогона)

- **`.gitattributes`** — иначе bash-скрипты, склонированные на Windows с
  `core.autocrlf=true`, приезжают в Linux-контейнер с CRLF и падают на
  `exec format error` / `bash\r: not found`:

  ```gitattributes
  *.sh    text eol=lf
  *.bash  text eol=lf
  *.yaml  text eol=lf
  *.yml   text eol=lf
  *.ps1   text eol=crlf
  *.psm1  text eol=crlf
  *.bat   text eol=crlf
  ```

  На машине агента дополнительно: `git config --global core.autocrlf false`.

- **`.gitignore`** — `node_modules/`, `dist/`, `venv/`, `__pycache__/`,
  `.pytest_cache/`, `.ruff_cache/`, `playwright-report/`, `test-results/`,
  `coverage.xml`, `.env`.
- **`.dockerignore`** в каждом контексте сборки: без него в образ попадают
  venv, кэши и отчёты тестов (и образ раздувается на сотни мегабайт).
- **`.env` не в репозитории**, только `.env.example`; секреты — в переменных
  CI/CD (§7).
- **`.gitleaks.toml`** — allowlist для заведомо несекретных тестовых значений
  (`test_pass`, `ci_secret_key_do_not_use_in_production`), чтобы job `gitleaks`
  не краснел на самом конфиге.

---

## 4. Шаг 2. Инвентаризация проверок

Выпишите, что уже запускается локально, и разложите по трём корзинам:

| Корзина | Критерий | Куда |
|---|---|---|
| Быстрое и детерминированное | линтеры, юнит-тесты, сборка — минуты, без GUI | Docker-агент |
| Нужен реальный сервис | БД, Redis, брокер | Docker-агент + `services` |
| Нужен Windows/GUI/локальный Docker | Playwright с браузерами, `docker build` на хосте | PowerShell-агент |

Правило: **всё, что можно выполнить в контейнере, выполняется в контейнере** —
это воспроизводимо и не зависит от того, что установлено на хосте. Хост нужен
только там, где контейнер принципиально не подходит.

Типовой набор для такого же стека (наш референс):

```bash
# backend
cd backend && ruff check app tests scripts
cd backend && mypy app --config-file ../pyproject.toml
cd backend && alembic upgrade head && alembic check
cd backend && pytest -q --cov=app

# frontend
cd frontend && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm test && pnpm build

# сборка
docker build -t app-backend ./backend
docker build -t app-frontend ./frontend
docker compose -f docker-compose.prod.yml config --quiet
```

> Если команды уже вынесены в `scripts/ci/*.sh|ps1`, переносите их в GitFlic
> как есть: один и тот же скрипт должен работать и локально, и в CI. Дублирование
> команд в YAML — главная причина, почему CI и локальная проверка расходятся.

---

## 5. Шаг 3. Конфиг конвейера

### 5.1. Соответствие привычным CI

| GitHub Actions | GitLab CI | GitFlic |
|---|---|---|
| `runs-on: ubuntu-latest` | `tags:` | `tags:` (теги агента) |
| `uses: actions/checkout` | автоматический клон | клон делает агент, шага нет |
| `uses: <action>` | `include:`/скрипты | только shell-команды в `script` |
| `services:` | `services:` | `services:` (без `options`/healthcheck) |
| `env:` / `secrets` | `variables` | `variables` + переменные проекта (перекрывают YAML) |
| `cache:` | `cache:` | `cache:` (ключ — **список** строк) |
| `timeout-minutes` | `timeout` | нет ключа: настройка «Task Restart Timeout» в проекте |
| `on: pull_request` | `rules:` | `workflow:rules:` + `$CI_PIPELINE_TYPE` |
| `gh release create` | `release:` | `release:` (после проверки) |
| `gh` CLI | `glab` | API GitFlic / CLI |

### 5.2. Скелет

```yaml
stages: [lint, test, security, e2e, docker, release]

workflow:
  rules:
    - if: $CI_PIPELINE_TYPE == "merge_request_pipeline" || $CI_PIPELINE_TYPE == "merge_result_pipeline"
      when: always
    - if: $CI_PIPELINE_TYPE == "branch_pipeline" && $CI_COMMIT_REF_NAME == $CI_DEFAULT_BRANCH
      when: always
    - if: $CI_PIPELINE_TYPE == "tag_pipeline" && $CI_COMMIT_TAG
      when: always
    - when: never

variables:
  PIP_CACHE_DIR: ".pip-cache"   # только относительные пути: кэш живёт в клоне
  PYTHONUNBUFFERED: "1"

lint:
  stage: lint
  image: python:3.12-slim
  tags: [docker]
  cache:
    key: [pip]                  # список, не строка
    paths: [.pip-cache]
  script:
    - pip install -r backend/requirements.txt
    - cd backend && ruff check app tests scripts
```

Полный готовый пилот — в Приложении A, структура полного конфига — в
Приложении B.

### 5.3. Шесть отличий, которые ломают конфиг

1. **Нет `runs-on` и `uses`.** Вместо `runs-on` — `tags`. Вместо action'ов —
   shell-команды. `checkout` не нужен: агент клонирует сам.
2. **`image`/`services` — только Docker-агент.** PowerShell-агент `image`
   игнорирует и выполняет скрипт на хосте. Job без `image`, но с `tags: [docker]`
   тоже уедет в контейнер — следите за парой.
3. **У `services` нет `options`/healthcheck.** Готовность БД ждём retry-циклом в
   `before_script` (см. Приложение A). Неизвестно, пробрасываются ли переменные
   job'а в контейнеры сервисов — **это первое, что проверяется на живом
   прогоне**; если нет, сервис поднимется с дефолтным паролем, и тест упадёт с
   понятной ошибкой «БД открыта, но вход не удался».
4. **Переменные проекта перекрывают `variables` из YAML.** Заведёте в проекте
   `POSTGRES_HOST=127.0.0.1` для e2e — job `test` получит этот адрес вместо
   сервиса `postgres`. Лечится префиксами (`E2E_*`) и явным `export` в
   `before_script`.
5. **Нет `timeout` у job.** Лимит и перезапуск — «Task Restart Timeout» в
   настройках CI/CD (поставьте 1800–2400 с) и авт cancel устаревших пайплайнов.
6. **`cache.key` — список строк, пути только относительные.** Абсолютный путь
   (`/root/.cache/pip`) не сработает; кэш локальный на агенте, общий только
   между job'ами одного агента.

Дополнительно: `needs: []` (приём GitHub/GitLab) в GitFlic не документирован —
порядок задавайте через `stages`, а `needs` оставьте только там, где он реально
нужен (`test` после `lint`, `e2e`/`docker` после `test`).

---

## 6. Шаг 4. Агенты

### 6.1. Docker-агент (обязателен)

Нужен для всех job'ов с `image`/`services`.

```properties
# config/application.properties
runner.executor=docker
docker.host=npipe:////./pipe/docker_engine   # Docker Desktop на Windows
docker.didEnable=false                        # DinD не включаем
docker.privileged=false                       # true — только если нужен docker:dind
docker.networkMode=host
# Зеркало/реестр: снимает лимиты Docker Hub
docker.registry-url=https://registry.gitflic.ru
docker.registry-username=<gitflic username>
docker.registry-password=<transport token>
logging.file.name=data/log/server.log
```

Регистрация:

```powershell
java -jar runner.jar register --url "<URL из UI>" `
  --registration-token "<Token из UI>" `
  --name "app-docker" --tags "docker"
```

### 6.2. PowerShell-агент (для e2e и docker build)

Нужен, если есть Playwright/e2e или сборка через Docker Desktop.

```properties
runner.executor=powershell
logging.file.name=data/log/server.log
logging.level.root=INFO
```

Регистрация — с тегом `windows-dev`:

```powershell
java -jar runner.jar register --url "<URL>" --registration-token "<Token>" `
  --name "app-windows-dev" --tags "windows-dev"
```

Запуск — **в сессии пользователя**, у которого есть Docker Desktop и браузеры.
Служба `LocalSystem` не видит пользовательский npipe и профиль с браузерами.
Для автозапуска — задача планировщика «при входе в систему»:

```powershell
$runnerDir = "$env:USERPROFILE\gitflic-runner"
$action  = New-ScheduledTaskAction -Execute "java.exe" `
  -Argument "-jar runner.jar start --config=config/application.properties" `
  -WorkingDirectory $runnerDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
Register-ScheduledTask -TaskName "GitFlic Runner (windows-dev)" `
  -Action $action -Trigger $trigger -Force
```

### 6.3. Теги и ожидание задач

- Тег в YAML должен **точно** совпадать с тегом агента (`docker`, `windows-dev`).
- «Run untagged jobs» держите **выключенным**: все job'ы тегированы явно,
  случайных захватов не будет.
- Job в статусе «ожидание исполнителя» при online-агенте — это всегда
  несовпадение тега или отсутствие нужного типа агента.

### 6.4. Безопасность

- Агент = удалённое выполнение кода на вашей машине. Отдельная учётка, никакого
  администратора (для Docker достаточно `docker-users`), машина обновляется,
  порты наружу не открываются.
- `config/application.properties` содержит токен агента: ограничить ACL
  каталога, не коммитить, при компрометации — удалить агента в UI и
  зарегистрировать заново.
- Не запускать пайплайны из недоверенных форков с секретами.

---

## 7. Шаг 5. Переменные и секреты

Всё, что является секретом или адресом окружения, — в **CI/CD проекта**, не в
YAML. Значения с галочкой **Mask** в логах заменяются на `***`.

| Имя | Пример | Mask | Зачем |
|---|---|---|---|
| `SECRET_KEY` | случайная строка ≥ 32 символов | да | JWT в тестах и e2e |
| `POSTGRES_PASSWORD` | пароль тестовой/локальной БД | да | job `test` и `e2e` |
| `E2E_PYTHON` | `C:\...\backend\venv\Scripts\python.exe` | нет | e2e, если PyPI на хосте недоступен |
| `E2E_POSTGRES_PORT` | `5434` | нет | e2e: локальный Postgres |
| `E2E_REDIS_PORT` | `6381` | нет | e2e: локальный Redis |
| `REGISTRY_USER` / `REGISTRY_TOKEN` | логин + transport token | да | push образов (§8.5) |

Чего **не** делать:

- не заводить в проекте `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_USER`/
  `POSTGRES_DB`/`REDIS_HOST`/`REDIS_PORT` — они перекроют YAML у job `test`
  (см. §5.3, п. 4);
- не класть `.env` и токены в репозиторий;
- не печатать секреты в `echo` — маска помогает не всегда (например, при
  посимвольной сборке строки).

---

## 8. Шаг 6. Сборка

Сборка — самая «железная» часть переноса. Три принципа: слои кэшируются,
зависимости ставятся офлайн-надёжно, конфигурация проверяется до запуска.

### 8.1. Backend-образ

```dockerfile
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# Индекс PyPI параметризован: в CI передаём зеркало/локальный индекс
ARG PIP_INDEX_URL=https://pypi.org/simple/
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url $PIP_INDEX_URL -r requirements.txt

COPY . .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Что важно:

- `requirements.txt` копируется **до** исходников — слой с зависимостями
  переиспользуется, пока не изменился файл;
- `PIP_INDEX_URL` — build-arg, а не хардкод: на машине агента PyPI может быть
  недоступен, в CI подставляется зеркало;
- entrypoint применяет миграции Alembic до старта API — иначе на чистой БД
  приложение падает;
- `.dockerignore` обязателен.

### 8.2. Frontend-образ

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --allow-build=esbuild
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

Нюансы pnpm 12:

- `--frozen-lockfile` — обязателен в CI: ловит расхождение lock-файла и
  `package.json`;
- `--allow-build=esbuild` (и `onlyBuiltDependencies` в `pnpm-workspace.yaml`) —
  иначе `ERR_PNPM_IGNORED_BUILDS`;
- версия pnpm фиксируется `corepack prepare pnpm@12 --activate`, с fallback
  `corepack install --global pnpm@12`.

### 8.3. Валидация prod-compose

Проверка «конфиг собирается и подстановки не пустые» стоит секунды и ловит
опечатки в `docker-compose.prod.yml`:

```bash
POSTGRES_PASSWORD=change_me_password SECRET_KEY=ci_secret_key_do_not_use_in_production \
  docker compose -f docker-compose.prod.yml config --quiet
```

Если в compose используются `:?`-подстановки, в CI подставьте заглушки —
реальный деплой этим job'ом не выполняется.

### 8.4. Зависимости и кэш

Порядок, который не зависит от удачи с сетью:

1. **Wheelhouse** — локальный каталог (или named volume) с колёсами под Linux:
   `pip install --no-index --find-links /wheelhouse -r requirements.txt`. Быстро,
   офлайн, детерминированно. Собирается один раз:
   `pip download -r requirements.txt -d wheelhouse --only-binary=:all: --platform manylinux2014_x86_64`.
2. **Зеркало PyPI** (`PIP_INDEX_URL`), если wheelhouse неполный.
3. `pypi.org` — последним, с короткими таймаутами (`PIP_DEFAULT_TIMEOUT=30`,
   `PIP_RETRIES=2`): при недоступности pip «залипает» на TLS на десятки минут.

Кэш в GitFlic — локальный на агенте:

```yaml
cache:
  key: [pip]            # список
  paths: [.pip-cache]   # относительный путь внутри клона
```

Для pnpm — `paths: [frontend/.pnpm-store]` и `pnpm install --store-dir .pnpm-store`.
Первый прогон всегда холодный; сброс кэша — в UI (права Administrator+).

### 8.5. Публикация образов в registry GitFlic

Если нужна не только сборка, но и хранение образов — используйте встроенный
реестр `registry.gitflic.ru` (путь зависит от уровня: проект/компания/инстанс;
проверьте фактический на первом `push`).

```yaml
build-push:
  stage: docker
  image: docker:27-cli
  tags: [docker]
  variables:
    IMAGE: registry.gitflic.ru/<company>/<project>/backend
  script:
    - echo "$REGISTRY_TOKEN" | docker login registry.gitflic.ru -u "$REGISTRY_USER" --password-stdin
    - docker build -t "$IMAGE:$CI_COMMIT_SHORT_SHA" -t "$IMAGE:latest" ./backend
    - docker push "$IMAGE:$CI_COMMIT_SHORT_SHA"
    - docker push "$IMAGE:latest"
  rules:
    - if: $CI_COMMIT_REF_NAME == $CI_DEFAULT_BRANCH
```

Замечания:

- на Docker-агенте с DinD нужен `privileged=true` — а это риск; проще держать
  job сборки на том же Docker-агенте, который уже имеет доступ к демону, либо
  на PowerShell-агенте через `docker build`/`push` хоста;
- `docker login` — только через `--password-stdin`, токен — в маскированной
  переменной;
- `latest` двигайте только с default-ветки, иначе тег будет указывать на
  случайный коммит;
- retention (автоудаление старых тегов) может отсутствовать — заложите очистку
  по расписанию или не пушьте каждый коммит.

### 8.6. Артефакты и квота

- В артефакты кладите только то, что нужно для разбора падения:
  `frontend/playwright-report` (7 дней), `notes.md` для релиза.
- `dist/`, `coverage.xml`, `node_modules` — не выкладывать: бандл пересобирается
  за десятки секунд, а артефакты тратят квоту.
- `when: always` у отчёта e2e — иначе при падении отчёта не будет.

### 8.7. Скорость сборки

- `DOCKER_BUILDKIT=1` и cache mount для пакетных менеджеров заметно сокращают
  повторную сборку;
- Docker-слои живут на хосте агента между прогонами — не пересоздавайте демон
  без нужды;
- на одном агенте job'ы идут последовательно: шесть-семь Docker-job'ов подряд
  могут дать 15–20 минут вместо 8–10 (это нормальная цена одномашинного
  пилота, а не ошибка конфига).

---

## 9. Шаг 7. Гейты: MR и защита ветки

1. **CI/CD → Enable Merge Request Pipeline** — MR-пайплайн запускается на
   изменениях запроса на слияние.
2. **Защита ветки `main`**: запрет прямого push, запрет force-push.
3. **«Проверять статус последнего конвейера при слиянии запроса»** — включить.
   Это и есть аналог required checks.
4. **Проверить гейт на живом MR:** во временной ветке намеренно сломать job
   (например, `exit 1` в линтере), убедиться, что MR-пайплайн красный и кнопка
   merge недоступна.
5. Если гейт не работает (тариф/баг) — резервный путь: webhook/API-скрипт,
   который по статусу пайплайна ставит label и снимает approval; решение
   зафиксировать в документации проекта.

Пока гейт не включён, работает правило «мерж только при зелёном CI» —
проверка глазами. Это хуже, чем автоматика, и должно быть временным.

---

## 10. Шаг 8. Первый прогон и приёмка

### 10.1. Порядок

1. Один Docker-агент + пилотный конфиг (`lint`, `test`) — проверяем, что
   платформа запускает задачи, сервисы поднимаются, секреты маскируются.
2. PowerShell-агент + полный конфиг — добавляем `e2e`, `docker`, `security`.
3. MR-пайплайн + гейт — проверяем на тестовом MR.
4. Тег → job `release` → релиз (сначала dry-run).

Не включайте всё сразу: если первый прогон красный из-за незарегистрированного
второго агента, вы будете чинить не то.

### 10.2. Критерии приёмки

| # | Критерий | Как проверить |
|---|---|---|
| 1 | Ветки, теги, коммиты совпадают с источником | `git log`, UI |
| 2 | Агент забирает задачи, `lint` и `test` зелёные | статус job'ов |
| 3 | `test` видит Postgres/Redis через `services` | лог wait-цикла |
| 4 | Секреты маскируются, `.env` не в репозитории | лог, `git ls-files` |
| 5 | MR-пайплайн создаётся, красный блокирует merge | тестовый MR |
| 6 | Время MR-пайплайна ≤ 15 минут | тайминги job'ов |
| 7 | e2e стабилен 2 прогона подряд | история пайплайнов |
| 8 | Сборка образов и `compose config` зелёные | job `docker` |
| 9 | Тег → `release` собирает заметки | tag-пайплайн |

### 10.3. Ориентировочные тайминги (одна машина)

| Job | Холодный | С кэшем |
|---|---|---|
| `lint` | 1,5–2,5 мин | 1–1,5 мин |
| `test` | 6–9 мин | 5–7 мин |
| `frontend` | 2,5–4 мин | 1,5–2,5 мин |
| `security-*` | 0,5–2 мин | 0,5–2 мин |
| `gitleaks` | 0,5–1 мин | 0,5–1 мин |
| `e2e` | 2–3 мин | 2–3 мин |
| `docker` | 3–6 мин | 2–4 мин |

---

## 11. Грабли: симптом → причина → решение

| Симптом | Причина | Решение |
|---|---|---|
| Job висит «в ожидании исполнителя» | тег job'а не совпадает с тегом агента, либо нет агента нужного типа | сверить `tags` в YAML и в UI агента; для `image`/`services` нужен Docker-агент |
| `runner.executor is not declared` | в `application.properties` нет `runner.executor` | добавить `docker` или `powershell`, перезапустить |
| `Cannot connect to the Docker daemon` | Docker Desktop не запущен или npipe недоступен пользователю агента | запустить Docker Desktop в сессии пользователя; добавить в `docker-users`; не запускать службой от `LocalSystem` |
| `exec format error` / `bash\r: not found` | CRLF в скриптах после клона на Windows | `.gitattributes` с `eol=lf` для `.sh`/`.yaml`, `core.autocrlf false` на агенте |
| `PostgreSQL ... не открылся за 60 с` | сервис не стартовал или не тот alias | проверить `services.name`/`alias`, лог сервиса |
| `БД открыта, но вход не удался` | пароль сервиса и клиента разный | один источник пароля (переменная проекта) для сервиса и job'а |
| `extension "vector" is not available` | образ Postgres без pgvector | `pgvector/pgvector:pg17`, не `postgres:*` |
| `pull access denied` / rate limit | лимиты Docker Hub | `docker.registry-*` на `registry.gitflic.ru`, `runner.helperImage` |
| `ERR_PNPM_IGNORED_BUILDS` | pnpm 12 блокирует postinstall | `--allow-build=esbuild` + `onlyBuiltDependencies` |
| `corepack prepare pnpm@12` падает | нет сети до npm registry у агента | проверить прокси; fallback `npm i -g pnpm@12` |
| e2e: `Executable doesn't exist ... playwright` | браузеры не установлены у пользователя агента | `pnpm exec playwright install chromium` под этим пользователем |
| e2e: `EADDRINUSE :8001/:3100` | зависшие процессы с прошлого прогона | закрыть uvicorn/vite, перезапустить агента |
| gitleaks краснеет на тестовом пароле | секрет-заглушка в конфиге | allowlist в `.gitleaks.toml`, не отключать правила |
| Кракозябры в логах Windows-агента | кодировка консоли | `logging.charset.console=windows-1251`, UTF-8 в профиле PowerShell |
| Первый прогон очень долгий | холодный кэш, pull образов | это нормально; второй прогон быстрее |

---

## 12. Ограничения и стоимость

- **Свои агенты обязательны:** облачные агенты GitFlic по умолчанию выключены.
  Машина выключена — CI стоит. Это single point of failure, планируйте
  резервную машину или дежурство.
- **Free-тариф:** приватные репозитории до 5 человек, 4 ГБ на репозиторий,
  CI/CD включён. Company — от 750 ₽/чел/мес, self-hosted Community — 0 ₽ плюс
  сервер. Цифры проверяйте на `gitflic.ru/price` перед решением.
- **Зеркало GitHub ↔ GitFlic** в облаке — по запросу в поддержку, обновление
  примерно раз в сутки.
- **Gitleaks** как встроенная интеграция — только в self-hosted; на SaaS это
  обычный job с образом (как в Приложении B).
- **SAST/DAST, merge trains, аудит** — платные тарифы; на Free доступен
  MR-пайплайн.
- **Экосистема:** нет marketplace action'ов — каждый шаг пишется руками. Это
  главная статья трудозатрат при переносе.
- **Merge Result Pipeline** — Enterprise-функция; на Free рассчитывайте на
  MR-пайплайн.

---

## 13. Чек-лист передачи (для принимающей стороны)

- [ ] Репозиторий импортирован, ветки/теги/коммиты сверены, PAT отозван.
- [ ] `.gitattributes` (LF/CRLF), `.gitignore`, `.dockerignore`, `.gitleaks.toml` на месте.
- [ ] Команды проверок вынесены в `scripts/ci/*` и работают локально.
- [ ] `gitflic-ci.yaml` (полный) и `ci/gitflic-pilot.yaml` (пилот) лежат в репозитории.
- [ ] Docker-агент зарегистрирован с тегом `docker`, статус Active.
- [ ] PowerShell-агент зарегистрирован с тегом `windows-dev` (или осознанно не нужен).
- [ ] «Run untagged jobs» выключен, теги в YAML = теги агентов.
- [ ] Переменные `SECRET_KEY`, `POSTGRES_PASSWORD` заведены с маской; `E2E_*` — без.
- [ ] `POSTGRES_HOST/PORT/USER/DB`, `REDIS_*` в проекте **не** заведены.
- [ ] Путь конфига в CI/CD указывает на нужный файл; MR-пайплайн включён.
- [ ] «Task Restart Timeout» 1800–2400 с; авто-отмена устаревших пайплайнов включена.
- [ ] Защита `main` (push/force-push) и проверка статуса конвейера при слиянии.
- [ ] Пилот `lint` + `test` зелёный, тайминги записаны.
- [ ] Полный пайплайн зелёный, e2e стабилен 2 прогона.
- [ ] Сборка образов и `compose config` зелёные; решение по registry принято.
- [ ] Гейт проверен на намеренно сломанном MR.
- [ ] Известные ограничения (§12) записаны в документацию проекта.

---

# Приложение A. Пилотный конфиг (готов к копированию)

Минимальный `ci/gitflic-pilot.yaml`: только Docker-агент, `lint` + `test`.
Точки адаптации помечены `# ←`.

```yaml
# Минимальный пилот GitFlic: lint + test. Путь указывается в CI/CD проекта.
stages: [lint, test]

workflow:
  rules:
    - if: $CI_PIPELINE_TYPE == "merge_request_pipeline" || $CI_PIPELINE_TYPE == "merge_result_pipeline"
      when: always
    - if: $CI_PIPELINE_TYPE == "branch_pipeline"
      when: always
    - if: $CI_PIPELINE_TYPE == "tag_pipeline" && $CI_COMMIT_TAG
      when: always
    - when: never

variables:
  PIP_CACHE_DIR: ".pip-cache"      # только относительный путь
  PYTHONUNBUFFERED: "1"

lint:
  stage: lint
  image: python:3.12-slim           # ← образ под ваш стек
  tags: [docker]
  cache:
    key: [pip]                     # ключ — список
    paths: [.pip-cache]
  before_script:
    - python -m pip install --upgrade pip
    # mypy нужны импортируемые пакеты, иначе сотни import-not-found
    - pip install -r backend/requirements.txt   # ← путь к requirements
  script:
    - cd backend && ruff check app tests scripts   # ← ваши команды
    - cd backend && mypy app --config-file ../pyproject.toml

test:
  stage: test
  image: python:3.12-slim
  tags: [docker]
  needs: [lint]
  services:
    # alias — hostname сервиса в сети job'а
    - name: pgvector/pgvector:pg17   # ← образ БД (pgvector обязателен для VECTOR)
      alias: postgres
    - name: redis:7-alpine
      alias: redis
  cache:
    key: [pip]
    paths: [.pip-cache]
  variables:
    # Несекретные дефолты; в проекте POSTGRES_PASSWORD перекроет значение
    POSTGRES_HOST: "postgres"
    POSTGRES_PORT: "5432"
    POSTGRES_USER: "test_user"
    POSTGRES_PASSWORD: "test_pass"
    POSTGRES_DB: "test_db"
    REDIS_HOST: "redis"
    REDIS_PORT: "6379"
    SECRET_KEY: "ci_secret_key_do_not_use_in_production"
    RATE_LIMIT_ENABLED: "false"
  before_script:
    - |
      set -eu
      # Явно фиксируем адреса сервисов: переменные проекта перекрывают YAML
      export POSTGRES_HOST=postgres POSTGRES_PORT=5432
      export REDIS_HOST=redis REDIS_PORT=6379

      python -m pip install --upgrade pip
      pip install -r backend/requirements.txt

      # healthcheck у services нет — ждём готовности сами
      python - <<'PY'
      import os, socket, sys, time
      import psycopg2

      host, port = os.environ["POSTGRES_HOST"], int(os.environ["POSTGRES_PORT"])
      deadline = time.monotonic() + 60
      while time.monotonic() < deadline:
          try:
              socket.create_connection((host, port), timeout=2).close()
              break
          except OSError:
              time.sleep(2)
      else:
          sys.exit(f"PostgreSQL {host}:{port} не открылся за 60 с")

      try:
          psycopg2.connect(
              host=host, port=port,
              user=os.environ["POSTGRES_USER"],
              password=os.environ["POSTGRES_PASSWORD"],
              dbname=os.environ["POSTGRES_DB"],
          ).close()
      except Exception as exc:
          sys.exit(f"PostgreSQL открыт, но вход не удался ({host}:{port}): {exc}")
      print(f"PostgreSQL готов: {host}:{port}")
      PY

      python - <<'PY'
      import os, sys, time
      import redis

      host, port = os.environ["REDIS_HOST"], int(os.environ["REDIS_PORT"])
      deadline = time.monotonic() + 60
      while time.monotonic() < deadline:
          try:
              if redis.Redis(host=host, port=port, socket_connect_timeout=2).ping():
                  break
          except Exception:
              time.sleep(2)
      else:
          sys.exit(f"Redis {host}:{port} недоступен за 60 с")
      print(f"Redis готов: {host}:{port}")
      PY
  script:
    - cd backend && alembic upgrade head
    - cd backend && alembic check      # модели == миграции
    - cd backend && pytest -q
```

---

# Приложение B. Структура полного конфига

Полный `gitflic-ci.yaml` (9 job'ов, включая `release`) — это тот же скелет плюс:

| Блок | Что добавить | Ключевые моменты |
|---|---|---|
| `frontend` | `image: node:22-alpine`, corepack pnpm 12, install/typecheck/lint/test/build | `cache.paths: [frontend/.pnpm-store]` |
| `security-backend` | `pip-audit -r backend/requirements.txt --strict` | сеть до PyPI/OSV обязательна |
| `security-frontend` | `pnpm audit --audit-level=high` | dev-only moderate не блокируют |
| `gitleaks` | `image: zricethezav/gitleaks`, `entrypoint: [""]` | `gitleaks git . --config .gitleaks.toml --redact` |
| `e2e` | `tags: [windows-dev]`, PowerShell-скрипт | `CI=true`, `E2E_PYTHON`, локальные Postgres/Redis |
| `docker` | `tags: [windows-dev]`, `docker build`, `compose config` | не блокировать job падением frontend-образа, если так задумано |
| `rules: changes:` у `e2e`/`docker` | docs-only изменения не гоняют дорогие job'ы | пути: `backend/**`, `frontend/**`, `scripts/**`, compose, сам YAML |
| `release` | `rules: if: $CI_COMMIT_TAG`, `python backend/scripts/release_notes.py` | `release:` включать после проверки на живом теге |

---

# Приложение C. Локальная проверка до первого прогона

Первый прогон на платформе — дорогая проверка. Дешевле прогнать команды
job'ов локально в тех же образах:

```bash
# 1. Валидация YAML (неизвестный ключ GitFlic не прощает)
python -c "import yaml,sys; d=yaml.safe_load(open('gitflic-ci.yaml')); print(list(d))"

# 2. Shell-блоки
sh -n scripts/ci/*.sh

# 3. Команды в тех же образах
docker run --rm -v "$PWD:/src" -w /src python:3.12-slim \
  sh -c "pip install -r backend/requirements.txt && cd backend && ruff check app tests scripts"
docker run --rm -v "$PWD:/src" -w /src node:22-alpine \
  sh -c "corepack enable && cd frontend && pnpm install --frozen-lockfile && pnpm build"

# 4. Сервисы как в job'е
docker network create ci-net
docker run -d --name postgres --network ci-net --network-alias postgres \
  -e POSTGRES_PASSWORD=test_pass -e POSTGRES_USER=test_user -e POSTGRES_DB=test_db \
  pgvector/pgvector:pg17
docker run -d --name redis --network ci-net --network-alias redis redis:7-alpine
```

Что всё равно проверяется только живым прогоном: проброс env в `services`,
глубина клона для gitleaks, поведение MR-пайплайна и гейта, кэш между
запусками, фактические тайминги.

---

# Приложение D. Ссылки

- Справочник `gitflic-ci.yaml`: <https://docs.gitflic.ru/latest/cicd/gitflic-ci-yaml/>
- Конвейеры и MR-пайплайны: <https://docs.gitflic.ru/latest/cicd/pipeline/>
- Настройки CI/CD проекта: <https://docs.gitflic.ru/latest/cicd/cicd-settings/>
- Кэш задач: <https://docs.gitflic.ru/latest/cicd/cache/>
- Типы агентов: <https://docs.gitflic.ru/latest/setup/runner/agent_types/>
- Установка PowerShell-агента: <https://docs.gitflic.ru/latest/setup/runner/installpowershell/>
- Установка Docker-агента: <https://docs.gitflic.ru/latest/setup/runner/installdocker/>
- Параметры `application.properties`: <https://docs.gitflic.ru/latest/setup/runner/app_prop/>
- Docker registry GitFlic: <https://docs.gitflic.ru/latest/registry/docker/>
- Импорт проекта: <https://docs.gitflic.ru/latest/project/import_base/>
- Зеркалирование: <https://docs.gitflic.ru/latest/project/mirror/>
- Тарифы: <https://gitflic.ru/price>
- Диагностика агента: <https://docs.gitflic.ru/latest/faq/faq_runner/>

Референсная реализация: `gitflic-ci.yaml`, `ci/gitflic-pilot.yaml`,
`docs/GITFLIC_RUNNER.md`, `docs/CI.md` в репозитории `ai-teacher_python`.
