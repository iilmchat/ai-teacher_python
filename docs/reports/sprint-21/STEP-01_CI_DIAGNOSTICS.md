# Шаг 01/спринт 21: диагностика CI и подготовка пилота GitFlic

**Дата:** 2026-10-30  
**Спринт:** 21 (v0.3.0 «Ops & Scale»)  
**Задача:** S21-001 (диагностика GitHub/KI-014) + подготовка S21-002/S21-003  
**Статус:** ✅ шаг выполнен; живой пилот GitFlic ждёт импорта репозитория и токенов
агентов (действия владельца).

---

## 1. Что сделано

1. Подтверждена причина падений GitHub Actions: аннотация check-run API run
   `41063439319` — «The job was not started because recent account payments have
   failed or your spending limit needs to be increased». Это `KI-014`.
2. Зафиксировано ограничение: `gh api /users/iilmchat/settings/billing/actions`
   требует scope `user` (у текущего токена: `gist, read:org, repo, workflow`),
   поэтому billing читается через веб-UI или `gh auth refresh -s user`.
3. Написан ADR `docs/CI.md`: варианты платформы, стоимость, критерии решения,
   порядок импорта приватного репозитория (PAT `repo`), план порта.
4. Портирован CI на GitFlic — `gitflic-ci.yaml` (8 job'ов, services
   Postgres/Redis, кэш, артефакты, workflow-rules, черновик release).
5. Написан рунбук `docs/GITFLIC_RUNNER.md` (PowerShell- и Docker-агенты,
   настройка проекта, переменные, тайминги, troubleshooting, ограничения).
6. Установлена Java 11 (нужна PowerShell-агенту): Temurin `11.0.32.1+1`,
   `%LOCALAPPDATA%\gitflic\jdk-11.0.32.1+1`; `java -version` работает из PATH
   через шим в `WindowsApps`.
7. Проверены команды job'ов локально в Docker (без живого GitFlic): frontend
   и backend-lint/test — см. §3. Найден и исправлен дефект с unpinned-линтерами.
8. Проверена доступность fallback-варианта: токен регистрации self-hosted
   runner GitHub выдаётся (`POST .../actions/runners/registration-token`).

---

## 2. Файлы

```
+ docs/CI.md                                   — ADR: диагностика, варианты, критерии, импорт
+ docs/GITFLIC_RUNNER.md                       — рунбук агентов и настройки проекта
+ gitflic-ci.yaml                              — пилотный CI для GitFlic
+ docs/reports/sprint-21/STEP-01_CI_DIAGNOSTICS.md — этот отчёт
~ docs/README.md                               — ссылка на CI.md
~ TODO_V0.3.md                                 — S21-001 в работе (ADR готов)
~ .github/workflows/ci.yml                     — pinned ruff/mypy и скоуп lint
~ gitflic-ci.yaml                              — pinned ruff/mypy и скоуп lint
```

---

## 3. Проверки

| Проверка | Команда/источник | Результат |
|----------|------------------|-----------|
| Причина падений CI | `gh api .../check-runs/<job>/annotations` (run 41063439319) | billing-аннотация, подтверждает KI-014 |
| Billing API | `gh api /users/iilmchat/settings/billing/actions` | 404: нужен scope `user` (инструкция в CI.md) |
| Приватность репозитория | `gh repo view --json visibility` | PRIVATE → для импорта нужен PAT |
| YAML GitFlic | `yaml.safe_load(gitflic-ci.yaml)` | ok; `stages` + 8 job-ключей |
| GitHub-only ключи | рекурсивный скан (`runs-on`, `uses`, `services.options`, `timeout-minutes`) | не найдены |
| Bash-блоки | `sh -n` в `python:3.12-slim` | ok |
| Frontend job | `node:22-alpine`: corepack pnpm@12 → install → typecheck/lint/test/build | **PASS**, 80/80, 78.71 kB gzip |
| Lint job (pinned) | `python:3.12-slim`, `ruff==0.8.1`, `mypy==1.13.0` | **PASS** 0/0 |
| Backend test job | `python:3.12-slim` + `services` pgvector/redis (aliases), alembic + pytest | **PASS**: 341 passed + 1 skipped, 106 с |
| E2E job (PowerShell-скрипт) | запуск скрипта job'а «как агент» на этой машине (`CI_PROJECT_DIR`, `E2E_PYTHON`, `POSTGRES_PASSWORD`, 5434/6381) | **PASS**: 12/12 e2e за 55 с, репорт создан |
| Docker job (PowerShell-скрипт) | `docker info`, `docker build` backend/frontend, `docker compose -f docker-compose.prod.yml config --quiet` | **PASS**: оба образа собраны, compose exit 0 |
| Java 11 | `java -version` | Temurin 11.0.32.1+1 |
| Fallback GitHub runner | `POST .../actions/runners/registration-token` | токен выдан (вариант A технически возможен) |

---

## 4. Проблемы и отклонения

1. **Unpinned-линтеры в CI:** `pip install ruff mypy` + `ruff check backend/`
   дают 54 ошибки на текущем коде (новые правила ruff 2026), тогда как
   `ruff==0.8.1` и скоуп `app tests scripts` — 0 ошибок. Исправлено в
   `gitflic-ci.yaml` и `.github/workflows/ci.yml`. GitHub не показывал проблему,
   т.к. job'ы не запускались (KI-014).
2. **winget не скачал JDK** (`InternetOpenUrl() failed`, aka.ms недоступен) —
   скачали Temurin 11 с GitHub Releases (github.com доступен).
3. **Java не было в PATH** — создан `java.cmd`-шим в
   `%LOCALAPPDATA%\Microsoft\WindowsApps` (каталог уже в PATH пользователя).
4. **Проброс env в `services` GitFlic не документирован** — главный риск пилота;
   в `test` добавлены wait-циклы с понятной ошибкой, если вход в Postgres не
   удастся.
5. **Docker Desktop останавливался** после предыдущих операций — перезапущен
   перед локальной проверкой; для живого пилота агент должен работать при
   запущенном Docker Desktop.

---

## 5. Новые KI

Нет. `KI-014` остаётся `Open` до выбора платформы (S21-002/S21-004).
Потенциальный новый KI заведём, если живой пилот выявит нерешаемое ограничение
(например, отсутствие env в `services`).

---

## 6. Обоснование решений

- **Сначала локальная проверка, потом живой GitFlic.** Облачных агентов нет,
  настройка проекта — ручная; дефект unpinned-линтеров нашёлся именно на этом
  шаге и стоил бы красного пайплайна в пилоте.
- **Пины линтеров, а не `--fix` под новые правила.** Проект фиксирует версии в
  `requirements.txt`; CI должен проверять тем же инструментом, что и разработчик
  (RULES §3.1). Апгрейд ruff — отдельное решение (S22).
- **Два агента (Docker + PowerShell).** В GitFlic нет `runs-on`; `image`/
  `services` исполняет только Docker-агент, а e2e/docker требуют Windows-хоста
  с Docker Desktop. Это осознанная конфигурация пилота, а не временный костыль:
  она проверяет оба пути.
- **Fallback GitHub — резерв, не первый шаг.** Регистрация runner'а возможна,
  но Windows-runner не умеет GitHub service containers; для `test`/`e2e`
  пришлось бы переписывать job'ы на docker-compose. GitFlic-путь при этом
  даёт RU-хостинг и не требует оплаты минут.
- **Секреты — только в переменных проекта с маской.** В `gitflic-ci.yaml`
  только несекретные дефолты (`test_pass` в allowlist `.gitleaks.toml`).

---

## 7. Что дальше

1. Владелец: создать PAT (fine-grained `Contents: Read` или classic `repo`),
   импортировать `iilmchat/ai-teacher_python` в GitFlic, отозвать PAT.
2. Владелец: прислать URL проекта GitFlic + registration tokens двух агентов
   (tags `docker` и `windows-dev`); либо GitFlic API token для автоматизации.
3. Lead: зарегистрировать агентов на этой машине, добавить переменные проекта
   (`SECRET_KEY`, `POSTGRES_PASSWORD`, `E2E_PYTHON`), включить MR-пайплайн,
   запустить пилот `lint`+`test`; проверить `services`, секреты, время.
4. S21-004: проверить, что красный MR-пайплайн блокирует merge (или gate через
   API/webhook), затем решение по платформе и отчёт спринта.
