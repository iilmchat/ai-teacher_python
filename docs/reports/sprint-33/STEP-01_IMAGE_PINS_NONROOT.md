# Шаг 01/спринт 33: digest-пиннинг образов и non-root backend

**Дата:** 2026-11-05  
**Спринт:** 33 (v0.4.0 «Production & Multi-node»)  
**Задача:** S33-001 (digest-пиннинг), S33-002 (non-root backend)  
**Статус:** ✅ выполнено

---

## 1. Что сделано

1. **Базовые образы закреплены по digest.** Тег оставлен для читаемости,
   digest фиксирует конкретный манифест:
   - `python:3.12-slim@sha256:b18b261e…31ab30` — `backend/Dockerfile`,
     `backend/sandbox_runner/Dockerfile`;
   - `node:22-alpine@sha256:fe4f6d74…699914` — build-stage frontend;
   - `nginx:1.27-alpine@sha256:65645c7b…2f2a10` — runtime frontend;
   - `pgvector/pgvector:pg17@sha256:7d0a4146…a9ccb8` — dev/prod compose;
   - `redis:7-alpine@sha256:8da19c73…0054d3f` — dev/prod compose.
2. **Backend работает под non-root.** Создан пользователь `app` (UID/GID
   `10001`, shell отключён), `COPY --chown=app:app`, `USER app`; `/app` для
   процесса read-only, запись — только в `/tmp` (и `PROMETHEUS_MULTIPROC_DIR`,
   если задан). Добавлены `PYTHONUNBUFFERED=1` и
   `PYTHONDONTWRITEBYTECODE=1`.
3. **Guard от регрессии.** `backend/scripts/check_image_pins.py` проверяет
   `FROM` в трёх Dockerfile'ах и `image:` в двух compose-файлах; вызов добавлен
   в `scripts/ci/backend-lint.sh` до установки зависимостей (скрипт — только
   stdlib).
4. **Тесты guard'а.** `backend/tests/test_image_pins.py`: 7 тестов (digest,
   `FROM`/`image:`, `scratch`, CLI-коды 0/1/2, реальное дерево репозитория).
5. **Проверена сборка и runtime:** backend, frontend, sandbox runner; полный
   `pytest` в собранном образе (Python 3.12, зависимости из
   `requirements.txt`), `alembic check`, `/health/ready`, compose-валидация.
6. **Документация:** `docs/RULES.md` §11.27 (политика digest/non-root),
   `TODO_V0.4.md` (спринт 33 — `[~]`, две задачи `[x]`), `CHANGELOG.md`
   (`[Unreleased]`).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests scripts` (из `backend/`) | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 92 файла |
| Тесты guard'а | `pytest -q tests/test_image_pins.py` | **7 passed** |
| Guard (хост) | `python backend/scripts/check_image_pins.py` | **OK**, 5 файлов |
| Guard (Python 3.12) | `docker run --rm -v "${PWD}:/src:ro" python:3.12-slim@sha256:b18b26… python /src/backend/scripts/check_image_pins.py --root /src` | **OK**, 5 файлов |
| Backend build | `docker build -t ai-teacher-backend:step33 ./backend` | **успех**; база — pinned digest |
| Frontend build | `docker build -t ai-teacher-frontend:step33 ./frontend` | **успех**; `tsc -b && vite build`, entry 79.98 kB gzip |
| Sandbox runner | `docker build -f backend/sandbox_runner/Dockerfile ...` + `--self-check` | **успех**; `uid=65534`, read-only, network none, caps 0 |
| Compose (dev) | `docker compose config --quiet` | **OK** |
| Compose (prod) | `docker compose -f docker-compose.prod.yml config --quiet` | **OK** |
| Non-root | `docker run --entrypoint id …` | `uid=10001(app) gid=10001(app)` |
| Запись в `/tmp` | `touch /tmp/step33-ok` | **OK** |
| `/app` read-only | `[ -w /app ]` | **false** (read-only) |
| Импорт приложения | `python -c "import app.main"` | **OK** |
| Полный pytest в образе | `docker run … python -m pytest -q -p no:cacheprovider tests` | **516 passed, 22 skipped** (201.58 с) |
| Alembic | `docker exec … alembic check` | `No new upgrade operations detected` |
| Health | `GET http://127.0.0.1:8000/health/ready` | **200**: `database=true`, `redis=true`, `version=0.3.3` |

Полный pytest выполнялся в образе `ai-teacher-backend:step33` (Python 3.12.16,
`fastapi 0.162.0` / `starlette 1.10.0`) с read-only-монтированием репозитория и
`-p no:cacheprovider`: локальный venv намеренно не использован, он отстаёт от
`requirements.txt` (KI-017, отчёт спринта 32).

---

## 3. Файлы

```
+ backend/scripts/check_image_pins.py              — guard digest-пиннинга
+ backend/tests/test_image_pins.py                 — 7 тестов guard'а
+ docs/reports/sprint-33/STEP-01_IMAGE_PINS_NONROOT.md — этот отчёт
~ backend/Dockerfile                               — digest, USER app, ENV, chown
~ backend/sandbox_runner/Dockerfile                — digest python
~ frontend/Dockerfile                              — digest node/nginx
~ docker-compose.yml                               — digest pgvector/redis
~ docker-compose.prod.yml                          — digest pgvector/redis
~ scripts/ci/backend-lint.sh                       — вызов guard'а в lint
~ TODO_V0.4.md                                     — S33-001/S33-002, статус
~ docs/CHANGELOG.md                                — [Unreleased]
~ docs/RULES.md                                    — §11.27
```

---

## 4. Проблемы и отклонения

1. **Первая сборка sandbox runner упала на зеркале PyPI.** `restrictedpython`
   не скачался с `mirrors.aliyun.com` (серия read timeout → «no matching
   distribution»). Повторная сборка со стандартным `pypi.org` прошла за 2 с.
   Это проявление **KI-017** (нестабильный PyPI), а не дефект Dockerfile;
   новый KI не заводился.
2. **Digest обновлён pull'ом, а не взят из старых локальных образов.**
   `docker pull` обновил `python`, `pgvector` и `redis`; в отчёт попали
   актуальные `RepoDigests`. Старые локальные образы остались, но новые
   контейнеры используют закреплённые digest'ы.
3. **CI-образы (`python`, `node`, `pgvector`, `redis`, `gitleaks`) пока не
   закреплены.** Шаг 01 закрывает образы, которые мы собираем и запускаем
   (backend/frontend/sandbox runner + compose). Пиннинг образов внутри
   workflow'ов и скриптов CI вынесен в следующий шаг вместе с `trivy`/
   `hadolint` — иначе пришлось бы менять 5 конфигов без возможности прогнать
   их локально.
4. **Официальный `nginx` по-прежнему запускает master под root.** Это
   стандартное поведение образа; worker'ы — `nginx`. Non-root для frontend не
   входил в задачу (статика за nginx, приложение не исполняется), при
   необходимости решается отдельным `nginxinc/nginx-unprivileged`-образом.
5. **Новых KI нет.** Открытые ограничения: `KI-017` (PyPI), `KI-023`
   (merge-gate), `KI-027` (отзыв JWT).

---

## 5. Обоснование решений

- **Digest, а не «immutable tag».** Docker Hub не гарантирует неизменность
  тегов; digest — единственная ссылка, которую можно проверить и передать в
  SBOM/сканер. Тег оставлен рядом (`python:3.12-slim@sha256:…`), чтобы человек
  понимал, что это за образ.
- **UID/GID `10001`, а не `nobody` (65534).** `nobody` уже используется
  песочницей (`--user 65534:65534`); разные роли не должны делить один UID.
  Фиксированный uid делает предсказуемыми права на volume'ах и в логах.
- **`/app` read-only, запись только в `/tmp`.** Процессу API не нужно писать в
  код; это уменьшает эффект компромисса. `PYTHONDONTWRITEBYTECODE=1` убирает
  единственную штатную запись (`__pycache__`) и шум в логах.
- **Guard на stdlib, а не `hadolint` уже сейчас.** `hadolint` проверяет стиль
  Dockerfile, но не знает про compose и требует отдельной установки; узкая
  проверка digest даёт немедленный гейт без новых зависимостей. `hadolint` и
  `trivy` — следующий шаг спринта.
- **Полный pytest в собранном образе.** Это проверяет не только код, но и
  реальный runtime (Python 3.12, pinned-зависимости, non-root, read-only
  монтирование). Локальный venv даёт ложные падения из-за старых
  `fastapi`/`starlette`.
- **CI-образы оставлены на следующий шаг осознанно.** Смешивать в одном
  коммите runtime-образы и 5 CI-конфигов — значит потерять проверяемость:
  workflow'ы нельзя прогнать локально, а `gitleaks:latest` требует отдельного
  digest и негативного теста.

---

## 6. Что дальше

1. **Шаг 02 спринта 33:** закрепить образы в CI (`ci-selfhosted.yml`, `ci.yml`,
   `release.yml`, `gitflic-ci.yaml`, `build-wheelhouse.ps1`), включая
   `gitleaks`; добавить `hadolint` и `trivy` (HIGH/CRITICAL → fail), расширить
   `check_image_pins.py` на workflow'ы.
2. **Шаг 03:** SBOM (CycloneDX) как артефакт релиза.
3. **Шаг 04:** `pre-commit` (ruff, gitleaks, i18n-аудит, `check_version`) и
   единые команды `Makefile`/`task`.
4. **PR:** ветка `sprint/33-supply-chain` → зелёный `CI (self-hosted fallback)`
   → merge в `main`; после мержа — `docker compose pull` на машинах
   разработчиков (образы БД/Redis сменятся на pinned digest).
