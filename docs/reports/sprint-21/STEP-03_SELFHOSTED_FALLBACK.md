# Шаг 03/спринт 21: self-hosted fallback CI проверен на GitHub

**Дата:** 2026-10-30  
**Спринт:** 21 (v0.3.0)  
**Задача:** S21-003 (вариант A), проверка fallback-пути  
**Статус:** ✅ fallback CI работает (6/6 job'ов зелёные); required checks на
GitHub Free невозможны → гейт остаётся за GitFlic (S21-004).

---

## 1. Что сделано

1. Установлен и зарегистрирован GitHub self-hosted runner на Windows-машине
   проекта (`ai-teacher-win`, version 2.338.2; labels `self-hosted, windows,
   ai-teacher`), запущен в фоне и подключён к GitHub.
2. Добавлен workflow `.github/workflows/ci-selfhosted.yml` (вариант A из
   `docs/CI.md`): 6 job'ов — `Lint (backend)`, `Test (backend)`, `Frontend`,
   `Security`, `E2E (Playwright)`, `Docker build`.
   - контейнерные job'ы (`python:3.12-slim`, `node:22-alpine`) — те же команды,
     что в GitFlic-конфиге, через переиспользуемые `scripts/ci/*.sh`;
   - `test` поднимает Postgres/Redis в отдельной docker-сети с alias
     `postgres`/`redis` (на Windows-runner service containers GitHub недоступны);
   - `e2e` и `docker` — нативно на Windows-хосте (Docker Desktop, Playwright,
     Node/pnpm).
3. Добавлены `scripts/ci/*.sh|ps1` и `.gitattributes` (LF для bash-скриптов,
   CRLF для PowerShell) — скрипты общие для fallback и GitFlic.
4. Настроены repo variable `E2E_PYTHON` и secrets `POSTGRES_PASSWORD`/`SECRET_KEY`
   (только для fallback; значения локальные, не production).
5. Первый прогон выявил дефект: lint-job ставил только ruff/mypy → mypy давал
   **295 ошибок** `import-not-found` (fastapi/sqlalchemy/structlog). Исправлено
   во всех CI-конфигах: lint ставит `backend/requirements.txt` (ruff/mypy там
   закреплены). Второй прогон — зелёный.

---

## 2. Файлы

```
+ .github/workflows/ci-selfhosted.yml        — fallback CI (self-hosted, Windows)
+ scripts/ci/backend-lint.sh                 — ruff+mypy в python:3.12-slim
+ scripts/ci/backend-test.sh                 — alembic + pytest с Postgres/Redis
+ scripts/ci/frontend.sh                     — typecheck/lint/test/build (node:22-alpine)
+ scripts/ci/security-backend.sh             — pip-audit (8 accepted ignores)
+ scripts/ci/security-frontend.sh            — pnpm audit --audit-level=high
+ scripts/ci/e2e.ps1                         — Playwright e2e на Windows-хосте
+ scripts/ci/docker.ps1                      — docker build + prod-compose config
+ .gitattributes                             — LF для .sh/.yaml, CRLF для .ps1/.cmd
+ docs/reports/sprint-21/STEP-03_SELFHOSTED_FALLBACK.md — этот отчёт
~ docs/CI.md                                 — §8: fallback проверен, ограничения
~ .github/workflows/ci.yml                   — lint ставит requirements (mypy)
~ gitflic-ci.yaml, ci/gitflic-pilot.yaml     — lint ставит requirements (mypy)
```

---

## 3. Проверки

| Проверка | Команда/источник | Результат |
|----------|------------------|-----------|
| Runner online | `GET /repos/.../actions/runners` | 1 runner, `status: online`, labels ок |
| Fallback CI run (1-й) | run `41069559937` | Frontend + Security ✅, Lint ❌ (mypy без deps) |
| Fallback CI run (2-й) | run `41070317162` | **все 6 job'ов success** |
| Lint | 2.4 мин | success |
| Test | 3.8 мин | success (341 passed + 1 skipped в контейнере) |
| Frontend | 1.0 мин | success (80/80, build) |
| Security | 1.5 мин | success (pip-audit, pnpm audit, gitleaks) |
| E2E | 2.2 мин | success (12/12) |
| Docker | 1.0 мин | success (build backend/frontend + compose config) |
| Branch protection | `GET /repos/.../branches/main/protection` | **403**: GitHub Free + private repo |

---

## 4. Проблемы и отклонения

1. **Required checks на GitHub Free недоступны** для приватного репозитория:
   `403 Upgrade to GitHub Pro or make this repository public`. Fallback даёт
   зелёный CI, но не блокирует мерж красного PR. Решение — GitFlic (бесплатно:
   защита веток + «Проверять статус последнего конвейера при слиянии»), см.
   `docs/CI.md` §8.
2. **`workflow_dispatch` из ветки спринта** GitHub не запускает, пока файла нет
   в default-ветке; для проверки временно добавлен триггер `push: [sprint/21-ci]`
   (в workflow помечено, после решения — `pull_request` + `push: main`, а
   fallback-триггер убрать или оставить только ручным).
3. **Первый прогон упал на mypy** (295 `import-not-found`) — исправлено
   установкой `backend/requirements.txt` в lint-job'ах (все конфиги).
4. **Windows-runner без service containers** — `test` поднимает Postgres/Redis
   вручную в docker-сети; e2e/docker — нативно. Это ограничение записано в
   `docs/CI.md`.
5. **GitFlic-проект импортирован** (`gitflic.ru/project/ruchating/ai-teacher_python`):
   доступны `main` (5a74145), `sprint/21-ci` (4fc8d37), `docs/*`, dependabot-ветки,
   теги v0.1.0/v0.2.0. Git-чтение анонимное (проект публичный) — требуется
   подтвердить, что публичность кода на GitFlic намеренна.

---

## 5. Новые KI

Нет. GitHub Free/private как ограничение платформы — часть аргументации ADR
(GitFlic), а не отдельный KI: required checks не являются обещанием GitHub Free.

---

## 6. Обоснование

- **Fallback сделан не «на всякий случай», а как проверка общих скриптов.**
  Job'ы fallback и GitFlic используют одни и те же `scripts/ci/*`, поэтому
  зелёный self-hosted прогон — это ещё и валидация будущего GitFlic-пайплайна
  на живом runner'е (за исключением `services`, которые в GitFlic исполняет
  Docker-агент).
- **Windows-runner: docker-обёртки вместо service containers.** GitHub не даёт
  service containers на Windows; ручная docker-сеть с alias даёт тот же контракт
  (`postgres`/`redis` как hostname) и совпадает с GitFlic `services`.
- **Не включаем required checks на GitHub.** Невозможно на Free/private;
  платить за Pro или публиковать репозиторий ради гейта — решение владельца, а
  не техническое. GitFlic закрывает это бесплатно.

---

## 7. Что дальше

1. **GitFlic (основной путь, S21-002):** нужен доступ к проекту — access token
   (scopes: `PROJECT_READ`, `PROJECT_EDIT`, `REPOSITORY_READ`, `REPOSITORY_WRITE`,
   `USER_READ`) **или** ручная настройка: CI/CD config path
   `ci/gitflic-pilot.yaml`, переменные `SECRET_KEY`/`POSTGRES_PASSWORD` (Mask),
   Docker-агент (tag `docker`) + его registration token.
2. Lead: зарегистрировать агент, запустить пилот, проверить `services`,
   маскировку, MR-пайплайн; затем включить опцию «Проверять статус последнего
   конвейера при слиянии» (S21-004) и переключиться на полный `gitflic-ci.yaml`.
3. Решение по fallback-триггеру: после GitFlic-пилота — либо оставить
   `workflow_dispatch`, либо включить `pull_request/push:main` как резервный
   зелёный CI (без required checks).
