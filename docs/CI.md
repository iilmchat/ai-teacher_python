# CI.md — CI-платформа: диагностика, варианты и решение (S21)

> Документ спринта 21 (v0.3.0). Закрывает `KI-014` (GitHub Actions не запускает
> job'ы) и фиксирует выбор CI-платформы: §1–§8 — диагностика и подготовка,
> §9 — итоговое решение (ADR), §10 — гейты и защита ветки, §11 — релиз,
> §12 — эксплуатация runner'а.
>
> Обновлено: 2026-10-31. Статус: **CI работает** — self-hosted runner, 6/6
> обязательных job'ов (плюс advisory `Perf smoke (submit)`, S23-003); merge-gate
> на GitHub Free/private недоступен (403) и обеспечивается GitFlic-пилотом
> (ждёт токен/агент владельца — `KI-023`).

---

## 1. Контекст и проверенные факты

**Симптом.** Все job'ы GitHub Actions завершаются за 0–2 с без выполнения шагов.
Пример: run `41063439319` (push, 2026-10-30T13:27:48Z) — `Lint (Backend)`,
`Security`, `Frontend` = failure, `Test (Backend)`, `Docker Build`,
`E2E (Playwright)` = skipped.

**Причина (подтверждена аннотацией API, а не только сообщением UI):**

```text
GET /repos/iilmchat/ai-teacher_python/check-runs/<job_id>/annotations
→ "The job was not started because recent account payments have failed or your
   spending limit needs to be increased. Please check the 'Billing & plans'
   section in your settings"
```

Это ровно `KI-014`: код, workflow и локальные гейты ни при чём (ruff/mypy/pytest,
frontend, e2e, docker — зелёные локально, см. `docs/reports/sprint-20/`).

**Ограничение доступа к биллингу из CLI.** Текущий токен `gh` имеет scopes
`gist, read:org, repo, workflow` — без `user`, поэтому:

```text
gh api /users/iilmchat/settings/billing/actions
→ 404 "This API operation needs the user scope"
```

Прочитать billing можно так:

- веб: GitHub → Settings → **Billing & plans** → Actions (минуты/лимит расходов);
- CLI (интерактивно, потребуется браузер): `gh auth refresh -h github.com -s user`,
  затем `gh api /users/iilmchat/settings/billing/actions`.

**Факт про наш репозиторий.** `iilmchat/ai-teacher_python` — **приватный**
(`visibility: PRIVATE`). Значит для импорта в GitFlic нужен GitHub-токен
(см. §6): без него GitFlic не вытянет приватный репозиторий.

**Что уже работает локально (не заменяет CI, но снимает риск «слепой» разработки):**
backend 341 passed + 1 skipped, ruff/mypy 0, `alembic check`; frontend 80/80,
build 78.71 kB gzip, `test:offline`; e2e 12/12; docker prod smoke 4/4 healthy.

---

## 2. Варианты CI-платформы

| Вариант | Стоимость | Плюсы | Минусы |
|---------|-----------|-------|--------|
| **A. GitHub + self-hosted runner** на машине проекта | 0 ₽ | нулевая миграция; PR checks, `gh`-скрипты, Releases остаются; за 1–2 часа разворачивается | зависимость от GitHub (биллинг/санкции); машина должна быть включена; GitHub Actions всё ещё требует минимальных минут для public/hosted — но self-hosted job'ы не тарифицируются |
| **B. GitFlic SaaS + свой агент** | 0 ₽ (≤5 человек, приватный репо 4 ГБ) | RU-хостинг; CI/CD в free-плане; GitLab-подобный `gitflic-ci.yaml` (`services`, DinD, cache, artifacts, MR-pipelines, release); импорт с GitHub; зеркала PULL/PUSH; реестр контейнеров/пакетов | облачные агенты по умолчанию выключены → нужен свой агент; зеркало в облаке раз в сутки и по разрешению поддержки; MR/issues/wiki не переносятся; Gitleaks-интеграция только в self-hosted; SAST/merge trains/аудит — платно |
| **C. GitFlic Self-hosted Community** | 0 ₽ + сервер (1 ядро/2 ГБ/10 ГБ, Java 11, PostgreSQL 11+, Redis 6+) | полный контроль и RU; unlimited users; CI/CD, агенты, LDAP/SSO OIDC | эксплуатация сервера, обновления, бэкапы — на нас |
| **D. GitLab CE self-hosted** | сервер | зрелый CI, полный перенос MR/issues (CE) | тяжёлая эксплуатация; избыточно для одного проекта |
| **E. Только локальные гейты** | 0 ₽ | ничего не нужно | нет required checks → регресс в `main`; не закрывает KI-014 |

Стоимость GitFlic (проверено на 2026-10-30): SaaS Free — публичные репо
безлимитно, приватные до 5 человек, 4 ГБ/репо, CI/CD включён; Company — от
750 ₽/чел/мес; Self-hosted Community — 0 ₽, Pro — от 243 000 ₽/год.

---

## 3. Решение (шаг 1): пилот GitFlic при сохранении GitHub как резерва

1. **Не блокировать v0.3.0 миграцией.** Пока CI не работает, гейты — локальные
   (RULES §10) + ручной чек-лист; это временно.
2. **Параллельный пилот GitFlic (S21-002):** импорт репозитория, PowerShell-
   или Docker-агент на машине проекта, минимальный `gitflic-ci.yaml` из 2 job'ов
   (`lint`, `test` с `services` Postgres/Redis), проверка MR-пайплайна и секретов.
3. **Fallback (вариант A):** self-hosted runner GitHub разворачивается, если
   пилот не даст паритета за 2 рабочих дня.
4. **Перенос origin в GitFlic** — только после выполнения критериев §5 и
   отдельным решением; до этого GitHub остаётся origin, GitFlic — пилот/зеркало.

**Почему так:** GitFlic закрывает стратегический риск (RU-хостинг, реестр
отечественного ПО, независимость от биллинга GitHub) и стоит 0 ₽ на нашем
масштабе, но требует своей инфраструктуры (агент) и имеет ограничения
(зеркала, MR-история, экосистема). Полный переезд без пилота — риск для релиза.

---

## 4. Как выглядит CI на GitFlic (план порта)

Файл `gitflic-ci.yaml` (в корне; путь настраивается в CI/CD проекта).
Соответствие job'ов:

| GitHub job | GitFlic job | Runner | Образ/сервисы |
|------------|-------------|--------|---------------|
| `lint` | `lint` | Docker-агент (Linux) | `python:3.12-slim` |
| `test` | `test` | Docker-агент | `python:3.12-slim` + `services: pgvector/pgvector:pg17, redis:7-alpine` |
| `frontend` | `frontend` | Docker-агент | `node:22-alpine` |
| `security` | `security-backend`, `security-frontend`, `gitleaks` | Docker-агент | `python:3.12-slim`, `node:22-alpine`, `zricethezav/gitleaks` |
| `e2e` | `e2e` | **PowerShell-агент** (Windows, `tags: [windows-dev]`) | host: Node/pnpm/Playwright/Docker Desktop |
| `docker` | `docker` | PowerShell-агент или DinD | host Docker / `docker:dind` |
| release (ручной) | `release` | Docker-агент | + `release:` keyword, gate по `CI_COMMIT_TAG` |

Особенности GitFlic, которые учтены в конфиге:

- нет GitHub-подобных `uses:`/`runs-on` — только `image` + `tags`;
- у `services` нет healthcheck-опций → в `before_script` ждём готовности
  `pg_isready`/`redis-cli ping` (retry-цикл);
- MR-пайплайн включается флажком в настройках CI/CD проекта; переменные
  `CI_PIPELINE_TYPE`/`CI_MERGE_REQUEST_*`;
- секреты — переменные проекта с маской (в файле только имена);
- кэш — локальный на агенте (или S3), ключ по lock-файлам;
- подпись/артефакты — `artifacts:paths`, `expire_in`;
- релизы — `release:` + GitFlic API/CLI (`gcli`), а не `gh`.

Руководство по установке агента и настройке проекта — `docs/GITFLIC_RUNNER.md`.

**Два конфига: пилот и полный.** Чтобы первый живой прогон не зависел от
второго (Windows) агента, в репозитории два файла:

| Файл | Job'ы | Когда использовать |
|------|-------|--------------------|
| `ci/gitflic-pilot.yaml` | `lint`, `test` (services Postgres/Redis) | первый прогон S21-002: только Docker-агент |
| `gitflic-ci.yaml` | все 8 job'ов (включая `e2e`/`docker`/`security`) | после регистрации PowerShell-агента (S21-003) |

Путь указывается в CI/CD проекта; после пилота переключается на полный. Пустой
`needs: []` (GitHub-приём) из полного конфига убран — в GitFlic он не
документирован, порядок задаётся `stages`; явные `needs` остались только у
`test`/`e2e`/`docker`.

---

## 5. Критерии решения (пилот GitFlic)

Пилот считается успешным, только если **всё** выполнено. Статус на 2026-10-30:

| # | Критерий | Статус |
|---|----------|--------|
| 1 | репозиторий импортирован: ветки/теги/коммиты совпадают с GitHub `main` | ✅ импорт выполнен (`gitflic.ru/project/ruchating/ai-teacher_python`, `main` = `5a74145`, ветки/теги видны) |
| 2 | агент забирает задачи, `lint` и `test` зелёные на нашем коде | ⏳ нужен агент (Java 11 + регистрация) |
| 3 | `test` видит Postgres/Redis через `services` (без ручных контейнеров) | ⏳ проверяется первым прогоном |
| 4 | секреты маскируются в логах, `.env` не попадает в репозиторий | ⏳ переменные с Mask создаёт `scripts/gitflic/setup.ps1` |
| 5 | MR-пайплайн создаётся автоматически и **красный пайплайн блокирует merge** | ⏳ S21-004, §10.3 |
| 6 | время PR-пайплайна ≤ 10 минут (5 job'ов, кэш) | ⏳ по таймингам §6 runbook'а — на грани |
| 7 | e2e на PowerShell-агенте стабилен (2 прогона подряд) | ⏳ e2e локально 12/12; на агенте — после регистрации |
| 8 | release dry-run: tag → job `release` → Release в GitFlic | ⏳ job `release` в `gitflic-ci.yaml` (тег-пайплайн) |

**Частично закрыто без доступа к GitFlic:** локальная валидация команд всех
job'ов в тех же Docker-образах (§8), готовые конфиги, ADR, скрипты установки
и настройки (`docs/GITFLIC_RUNNER.md`, `scripts/gitflic/setup.ps1`).

Если хотя бы один пункт не выполняется и не имеет внятного workaround — выбираем
вариант A (GitHub self-hosted runner), а GitFlic остаётся зеркалом/заделом на
будущее (KI-023 остаётся `Blocked` с планом).

---

## 6. Импорт приватного репозитория в GitFlic (для Lead/владельца)

Нужен **GitHub Personal Access Token** (PAT), потому что репозиторий приватный:

1. GitHub → Settings → Developer settings → **Personal access tokens**:
   - *Fine-grained* (рекомендуется): Repository access = только
     `iilmchat/ai-teacher_python`; Permissions → Repository permissions →
     **Contents: Read-only**; срок — 7–30 дней.
   - или *Tokens (classic)*: scope **`repo`** (полный доступ к приватным репо).
2. GitFlic → «+» → **Импорт проекта**:
   - URL: `https://github.com/iilmchat/ai-teacher_python.git`
   - Логин: `iilmchat`
   - Токен: PAT из п.1.
3. Проверить: ветка `main`, теги (`v0.2.0`), история коммитов, `.github/` (не
   исполняется, но пусть будет), затем включить CI/CD и указать
   `gitflic-ci.yaml`.
4. Пат **отозвать** сразу после импорта (он больше не нужен).
5. Зеркало GitHub↔GitFlic (опционально): в облаке создание зеркала требует
   прав — запросить в поддержке GitFlic; обновление раз в сутки.

> PAT — это пароль-заменитель для автоматизации; не коммитить, не пересылать
> в чатах, хранить в менеджере секретов. Для GitFlic-агента понадобится
> отдельный токен агента (его выдаёт GitFlic при регистрации агента).

---

## 7. Дальнейшие шаги (S21-003…S21-006) — статус

| Задача | Что сделано | Осталось |
|--------|-------------|----------|
| S21-003 GitHub-путь | `ci-selfhosted.yml`, 6/6 job'ов зелёные, кэш pip/pnpm (named volumes) | — |
| S21-003 GitFlic-путь | `gitflic-ci.yaml` (5 job'ов + 3 security), `ci/gitflic-pilot.yaml`, общие `scripts/ci/*` | живой прогон — S21-002 |
| S21-004 | path-фильтры (GitHub + GitFlic), `scripts/ci/protect-branch.ps1` | required checks на GitHub Free невозможны (403); MR-гейт — GitFlic (§10) |
| S21-005 | `release.yml` (гейты → тег → Release), dry-run, заметки из `RELEASES.md` | живой dry-run — после мержа/тега (§11) |
| S21-006 | этот документ, RULES §10, README-бейдж, KI-014/KI-023, отчёт спринта | — |

---

## 8. Локальная проверка job'ов до живого GitFlic (2026-10-30)

Облачных агентов у GitFlic по умолчанию нет, а первый прогон на платформе —
дорогая проверка. Поэтому команды job'ов прогнаны локально в тех же образах
Docker (репозиторий копируется в контейнер через `tar`, `venv`/`node_modules`
исключены; сервисы — отдельные контейнеры в сети с `alias postgres`/`redis`).

| Job | Как проверяли | Результат |
|-----|---------------|-----------|
| `frontend` | `node:22-alpine`: corepack pnpm@12, `pnpm install --frozen-lockfile`, typecheck/lint/test/build | **PASS**: 80/80 тестов, build 78.71 kB gzip (~3.5 мин) |
| `lint` | `python:3.12-slim`, `ruff==0.8.1` + `mypy==1.13.0`, `cd backend && ruff check app tests scripts`, `mypy app --config-file ../pyproject.toml` | **PASS** (0/0) |
| `test` | `python:3.12-slim` + `services` `pgvector/pgvector:pg17` (alias `postgres`) и `redis:7-alpine` (alias `redis`), wait-loops, `alembic upgrade head && alembic check`, `pytest -q` | **PASS**: **341 passed + 1 skipped** (106 с), миграции до `010` |
| `e2e` | PowerShell-скрипт job'а запущен на этом хосте «как агент»: `CI_PROJECT_DIR`, `E2E_PYTHON`, `POSTGRES_PASSWORD`, порты 5434/6381, Playwright webServer | **PASS**: **12/12** e2e за 55 с; Playwright-репорт создаётся |
| `docker` | скрипт job'а локально: `docker info`, `docker build` backend/frontend, `docker compose -f docker-compose.prod.yml config --quiet` | **PASS**: оба образа собраны, compose-валидация exit 0 |

**Найденный и исправленный дефект.** В старом CI (`ci.yml` и первичном порте)
линтеры ставились без версий (`pip install ruff mypy`), а ruff запускался как
`ruff check backend/`. На 2026-10-30 unpinned ruff даёт **54 ошибки** на том же
коде (новые правила upstream, напр. `UP042`/`C420`), тогда как закреплённый
`ruff==0.8.1` со скоупом `app tests scripts` — **0 ошибок**. GitHub Actions этот
дефект не показывал, потому что job'ы вообще не запускались из-за биллинга.
Версии закреплены в обоих конфигах: `gitflic-ci.yaml` и
`.github/workflows/ci.yml`.

**Что остаётся непроверяемым локально** (проверяется только живым пилотом):
проброс переменных окружения в `services` на стороне GitFlic, глубина
checkout'а для gitleaks, поведение MR-пайплайна и блокировка merge, теги
агентов/выбор исполнителя, межзапусковый кэш и артефакты.

**Fallback GitHub (вариант A) — реализован и проверен (2026-10-30).**
Workflow `.github/workflows/ci-selfhosted.yml` (self-hosted runner `ai-teacher-win`,
labels `self-hosted, windows, ai-teacher`) прогнан на этой машине: **все 6 job'ов
зелёные** — Lint 2.4 мин, Frontend 1.0, Security 1.5, Test 3.8, E2E 2.2,
Docker 1.0 (run
[41070317162](https://github.com/iilmchat/ai-teacher_python/actions/runs/41070317162)).
Job'ы используют те же команды, что и GitFlic-конфиг (`scripts/ci/*`), поэтому
это ещё и проверка общего набора скриптов. Триггеры: `pull_request`,
`push: main`, `workflow_dispatch` (до мержа спринта — также ветка `sprint/21-ci`,
см. комментарий в workflow).

Найдены и исправлены по ходу: mypy в lint-job'е требует установленных
runtime-зависимостей (295 `import-not-found`), поэтому lint ставит
`backend/requirements.txt`; bash-скрипты закреплены `.gitattributes` (LF).

**Ограничение варианта A:** на GitHub **free для приватного репозитория
недоступна защита ветвей/required checks** — API отвечает
`403 «Upgrade to GitHub Pro or make this repository public»`. То есть fallback
даёт зелёный CI, но не может *заблокировать* мерж красного PR без платного
плана (или публикации репозитория).

**GitFlic закрывает этот пробел на бесплатном тарифе:** в настройках проекта есть
защита веток (правила PUSH/MERGE, force-push, codeowners) и опция
«Проверять статус последнего конвейера при слиянии запроса» — мерж возможен
только при успешном последнем конвейере (MR-пайплайне). Это ровно тот гейт,
который нужен в S21-004; проверка на живом проекте — после токена/агента.

---

## 9. Итоговое решение (ADR, 2026-10-30)

**Контекст.** GitHub-hosted минуты заблокированы биллингом (`KI-014`); GitHub
Free для приватного репозитория не даёт branch protection (403 на API), т.е.
даже зелёный CI не может *заблокировать* мерж. GitFlic даёт и CI/CD, и защиту
ветвей на бесплатном тарифе, но требует своего агента и access token
(внешняя зависимость — у агента разработки их нет).

**Решение.**

1. **Немедленно — вариант A (сделано).** Self-hosted runner
   (`ai-teacher-win`, labels `self-hosted, windows, ai-teacher`) +
   переиспользуемые `scripts/ci/*`: `Lint (backend)`, `Test (backend)`,
   `Frontend`, `Security`, `E2E (Playwright)`, `Docker build`. Прогон 6/6
   зелёный (run
   [41070317162](https://github.com/iilmchat/ai-teacher_python/actions/runs/41070317162)).
   GitHub-hosted `ci.yml` переведён в ручной режим, чтобы не висеть красным.
2. **Цель — GitFlic как origin (v0.3.0).** `gitflic-ci.yaml` уже содержит порт
   5 job'ов + 3 security-job'а, MR-пайплайн, path-фильтры и job `release` для
   тегов; гейт мержа — опция «Проверять статус последнего конвейера при
   слиянии» (§10.3).
3. **Переезд origin** — отдельным решением после успешного пилота (§5);
   GitHub остаётся зеркалом.

**Почему не наоборот.** Платить за GitHub Pro или публиковать код ради гейта —
решение владельца, а не техническое; наш масштаб укладывается в бесплатные
тарифы обеих платформ. Гейт на GitHub включается одной командой
(`scripts/ci/protect-branch.ps1`) сразу после смены тарифа — путь назад открыт.

**Следствие для процесса.** Пока автоматический гейт не включён, зелёный
`CI (self-hosted fallback)` — обязательное условие мержа по RULES §10
(проверка глазами), а после S21-002/S21-004 станет автоматическим.

---

## 10. Гейты и защита ветки (S21-004)

### 10.1. Path-фильтры (сделано)

Docs-only изменение не гоняет ни e2e, ни docker, ни остальные job'ы:

- **GitHub:** `paths-ignore: ['docs/**', '**.md']` в `ci-selfhosted.yml`
  (и в ручном `ci.yml` — на будущее);
- **GitFlic:** `rules: changes: paths:` у `e2e` и `docker`
  (`backend/**`, `frontend/**`, `scripts/**`, `pyproject.toml`,
  `docker-compose*.yml`, `gitflic-ci.yaml`, `.gitleaks.toml`);
  `lint`/`test`/`frontend`/`security` идут всегда — они дешёвые и проверяют
  в том числе сам текст (gitleaks).

Проверка: PR, меняющий только `docs/**`, не запускает `CI (self-hosted
fallback)`; PR с кодом — запускает все 7 job'ов (включая perf-smoke).

### 10.2. GitHub: required checks — заблокировано тарифом

Факт (2026-10-30, повторно):

```text
GET /repos/iilmchat/ai-teacher_python/branches/main/protection
→ 403 "Upgrade to GitHub Pro or make this repository public to enable this feature."
```

То есть на GitHub Free + private нельзя ни включить required checks, ни
запретить force-push штатными средствами. Скрипт
`scripts/ci/protect-branch.ps1` содержит готовый набор и умеет:

```powershell
pwsh scripts/ci/protect-branch.ps1 -DryRun   # показать payload
pwsh scripts/ci/protect-branch.ps1 -Verify   # текущее состояние (403 → exit 1)
pwsh scripts/ci/protect-branch.ps1           # применить (403 → exit 3 + подсказка)
```

Требуемые проверки = имена job'ов fallback-CI: `Lint (backend)`,
`Test (backend)`, `Frontend`, `Security`, `E2E (Playwright)`, `Docker build`.
Плюс: PR-review (1 approval), запрет force-push и удаления ветки.

Включить гейт можно так (когда появится Pro или репозиторий станет публичным):
`pwsh scripts/ci/protect-branch.ps1`; после мержа спринта — заменить
`ai-teacher-pip-cache`-объёмы в workflow на кэш Actions, если вернёмся на
hosted-минуты.

### 10.3. GitFlic: MR-гейт (проверяется в пилоте)

1. CI/CD → **Enable Merge Request Pipeline** — MR-пайплайн запускается на
   изменениях запроса на слияние;
2. Настройки проекта → ветки: `main` — запрет прямых PUSH и force-push;
3. **«Проверять статус последнего конвейера при слиянии запроса»** — включить;
4. Проверить на тестовом MR: с намеренно красным job'ом кнопка merge должна
   быть недоступна. Если гейт не работает (баг/тариф) — резервный путь:
   webhook/API-скрипт, который по статусу последнего пайплайна ставит
   label/approval; результат записать в этот раздел.

Статус: ⏳ ждёт access token/агент владельца — `KI-023`.

---

## 11. Релиз (S21-005)

`.github/workflows/release.yml`:

| Шаг | Что делает |
|-----|-----------|
| Гейты | `uses: ./.github/workflows/ci-selfhosted.yml` — те же 6 job'ов, что в PR (команды не дублируются) |
| Версия | `backend/scripts/check_version.py --expected X.Y.Z` сверяет `pyproject.toml`, `frontend/package.json`, `backend/app/config.py`; в реальном релизе — `--strict` |
| Заметки | `backend/scripts/release_notes.py` берёт раздел «## Релиз vX.Y.Z» из `docs/RELEASES.md`; нет раздела — job падает |
| Dry-run | по умолчанию для `workflow_dispatch` и **всегда** для тега `v*-dryrun` |
| Релиз | `git tag -a vX.Y.Z` + `git push` + `gh release create --notes-file … --verify-tag` |

```bash
gh workflow run release.yml -f version=0.3.0                    # dry-run
gh workflow run release.yml -f version=0.3.0 -f dry_run=false    # реальный релиз
git tag v0.3.0-dryrun && git push origin v0.3.0-dryrun           # та же репетиция из тега
```

Почему тег `-dryrun`: репетиция проверяется на живом runner'е, а «настоящий»
тег не порождает второй прогон гейтов. Реальный релиз — только ручной запуск.

**Проверено живьём (2026-10-30):** тег `v0.2.0-dryrun` → run
[41126158359](https://github.com/iilmchat/ai-teacher_python/actions/runs/41126158359) —
гейты 6/6, «Версия: 0.2.0, dry-run: true», «OK: версия 0.2.0 согласована»,
«Заметки собраны», «DRY-RUN: тег и Release НЕ создаются». Тег после проверки
удалён. Ветка «реальный релиз» (создание тега и `gh release create`) впервые
будет пройдена на v0.3.0 (S30-004) — до этого её не тренируем на настоящих
номерах.

**GitFlic.** Job `release` (stage `release`, правило `if: $CI_COMMIT_TAG`)
включён в `gitflic-ci.yaml`: tag-пайплайн, проверка notes тем же скриптом,
`release:` — ключевое слово GitFlic. Ветку/MR он не затрагивает, поэтому его
первая проверка не мешает пилоту. При зеркалировании порядок: тег создаётся в
origin (GitFlic), зеркало GitHub догоняет.

**Откат.** Тег/релиз удаляются вручную (`gh release delete`, `git push
--delete`), версия в файлах откатывается коммитом; повторный выпуск с тем же
номером запрещён (job падает, если тег уже есть).

---

## 12. Эксплуатация CI (S21-006)

### 12.1. Runner

- Установка: `C:\actions-runner` (zip с
  `github.com/actions/runner/releases`), регистрация:
  `gh api -X POST repos/iilmchat/ai-teacher_python/actions/runners/registration-token`
  → `config.cmd --unattended --name ai-teacher-win --labels ai-teacher --replace`.
- Запуск: `run.cmd` **в сессии пользователя** (не LocalSystem!) — иначе нет
  доступа к Docker Desktop, Playwright-браузерам и npipe.
- Проверка: `gh api repos/iilmchat/ai-teacher_python/actions/runners` →
  `status: online`; процесс `Runner.Listener`.
- Логи: `C:\actions-runner\_diag\Runner_*.log` и `Worker_*.log`;
  stdout запуска — `C:\actions-runner\_logs\runner.log`.
- Машина выключена → job'ы в очереди (`queued`), это не ошибка кода.

### 12.2. Перезапуск и отмена

```bash
gh run list --limit 5
gh run rerun <run_id>              # перезапустить весь прогон
gh run rerun <run_id> --failed     # только упавшие job'ы
gh run cancel <run_id>             # отменить (например, залипший pip)
```

`concurrency` в `ci-selfhosted.yml` отменяет устаревшие прогоны той же ветки
(`cancel-in-progress: true`), поэтому новый push не ждёт старый.

### 12.3. Кэш и стоимость

- pip: named volume `ai-teacher-pip-cache` (`/root/.cache/pip` в контейнере) —
  PyPI с runner'а нестабилен (KI-017), без кэша каждая job качает колёса заново;
- pnpm: named volume `ai-teacher-pnpm-store`
  (`/workspace/frontend/.pnpm-store`);
- сброс кэша: `docker volume rm ai-teacher-pip-cache ai-teacher-pnpm-store`
  (следующий прогон — холодный);
- Playwright-браузеры лежат в профиле пользователя, docker-слои — в Docker
  Desktop; между прогонами не пересоздаются;
- self-hosted минуты GitHub не тарифицируются; цена — включённая машина.

### 12.4. Таймауты

Лимиты — `timeout-minutes` у job'ов (`lint` 15, `test` 30, `frontend` 20,
`security` 20, `e2e` 30, `docker` 25, `perf` 10); в GitFlic отдельного ключа
нет — `Task Restart Timeout` в настройках CI/CD проекта (1800–2400 с).

### 12.5. Если PyPI недоступен (KI-017)

Порядок установки зависимостей в job'ах (`scripts/ci/install-python-deps.sh`,
`security-backend.sh`):

1. `wheelhouse` (named volume `/wheelhouse`) — офлайн, основной путь;
2. зеркала `mirrors.aliyun.com` → `pypi.tuna.tsinghua.edu.cn`;
3. `pypi.org` — последним: когда он недоступен, pip «залипает» на TLS-таймаутах
   (наблюдалось 20+ минут на job `lint`).

`pip-audit` дополнительно переключается на advisory-сервис OSV
(`api.osv.dev`), если `pypi.org` не отвечает — набор находок совпадает
(16 ignored, exit 0).

Симптом: job `lint`/`test` висит на `pip install`, в логе — таймауты TLS.
Что делать:

1. `gh run cancel <id>`, затем `gh run rerun <id>` — сеть восстанавливается;
2. скрипты уже используют короткие таймауты (`PIP_DEFAULT_TIMEOUT=30`,
   `PIP_RETRIES=2`) и сначала идут на зеркала;
3. если не помогает — пересобрать wheelhouse
   (`pwsh scripts/ci/build-wheelhouse.ps1`) и повторить;
4. авторитетный «чистый» прогон — GitFlic/облачный агент, где PyPI доступен.

### 12.6. Параметры этой машины (2026-10-30)

| Что | Значение |
|-----|----------|
| Runner | `C:\actions-runner`, имя `ai-teacher-win`, labels `self-hosted, windows, ai-teacher` |
| Регистрация | `gh api -X POST repos/iilmchat/ai-teacher_python/actions/runners/registration-token` → `config.cmd --unattended --replace` |
| Запуск | `C:\actions-runner\run.cmd` **в сессии пользователя**; лог — `C:\actions-runner\_logs\runner.log`, диагностика — `_diag\` |
| Локальный compose | Postgres `5436`, Redis `6383` (канон 5434/6381 занят чужими контейнерами, KI-001); `.env` — локальный, в git не попадает |
| Repo secrets | `POSTGRES_PASSWORD`, `SECRET_KEY` — локальные значения, не production |
| Repo variables | `E2E_PYTHON=K:\Projects\AI\ai-teacher_python\backend\venv\Scripts\python.exe`, `E2E_POSTGRES_PORT=5436`, `E2E_REDIS_PORT=6383` |
| Кэши (volumes) | `ai-teacher-pip-cache`, `ai-teacher-pnpm-store`, `ai-teacher-wheelhouse` (69 МБ, 71 колесо) |
| venv для e2e | `backend\venv` (Python 3.12, зависимости из wheelhouse; в git не попадает) |

E2E-джоб поднимает `docker compose up -d postgres redis` сам и передаёт порты,
пользователя и пароль через окружение — `.env` в clone'е runner'а не нужен.

---

## 13. Зависимости и Dependabot (S22-004)

- **Dependabot** (`.github/dependabot.yml`): три экосистемы — pip (`/backend`),
  npm/pnpm (`/frontend`), GitHub Actions (`/`); еженедельно (пн, 06:00 MSK);
  minor/patch группируются в один PR на экосистему (`backend-minor-patch`,
  `frontend-minor-patch`), major приходят отдельно; лимит 5 открытых PR.
- **Политика мержа:** minor/patch — после зелёного `CI (self-hosted fallback)`;
  major — ручная проверка конфигов и полный прогон (контрактные тесты, e2e).
- **Авто-мерж недоступен** на GitHub Free/private (нет branch protection и
  auto-merge; см. KI-023) — мерж выполняет владелец по RULES §10.
- **После ручного апгрейда** (S22-002/003: fastapi/starlette/pytest) устаревшие
  PR закрыты, чтобы Dependabot пересобрал группы от актуальных пинов.
- **Порядок безопасного апгрейда** — RULES §11.21 (контрактные тесты →
  установка → pytest/e2e → пины → `pip-audit` без игноров → CHANGELOG/SPEC).

---

## 14. Ссылки

- Тарифы GitFlic: <https://gitflic.ru/price>
- Справочник `gitflic-ci.yaml`: <https://docs.gitflic.ru/latest/en/cicd/gitflic-ci-yaml/>
- Конвейеры и MR-пайплайны: <https://docs.gitflic.ru/latest/en/cicd/pipeline/>
- Агенты (runner): <https://docs.gitflic.ru/latest/en/setup/runner/agent_types/>
- Импорт проекта: <https://docs.gitflic.ru/latest/en/project/import_base/>
- Зеркалирование: <https://docs.gitflic.ru/latest/en/project/mirror/>
- Гайд по переносу с GitHub/GitLab: <https://habr.com/ru/companies/astralinux/articles/1042676/>
- GitHub Actions billing API: <https://docs.github.com/rest/billing/billing>
