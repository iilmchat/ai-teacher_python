# GETTING_STARTED — развёртывание за ~20 минут

Инструкция для разработчика, который впервые разворачивает проект на Windows
(для Linux/macOS отличия указаны в скобках).

---

## 1. Что нужно установить (≈10 мин)

| Инструмент | Версия | Проверка |
|------------|--------|----------|
| Python | 3.12 (3.11 тоже работает) | `python --version` |
| Node.js | 20+ | `node --version` |
| pnpm | 10+ (проверено на 12) | `pnpm --version` |
| Docker Desktop | актуальный | `docker --version` |

---

## 2. Клонирование и переменные окружения (≈2 мин)

```bash
git clone https://github.com/iilmchat/ai-teacher_python.git
cd ai-teacher_python
```

Скопируйте `.env` из шаблона:

```powershell
Copy-Item .env.example .env            # Windows
# cp .env.example .env                 # Linux/macOS
```

Заполните обязательные значения в `.env`:

- `SECRET_KEY` — любая длинная случайная строка (для JWT);
- `POSTGRES_PASSWORD` — пароль БД;
- `DEEPSEEK_API_KEY` — ключ DeepSeek (необязательно: без него чат вернёт 503,
  а health покажет `not_configured`);
- `LLM_FALLBACK_PROVIDER` — резервный провайдер (необязательно, например
  `lm_studio`): при сбое основного ответит он;
- `LM_STUDIO_URL` и `LM_STUDIO_MODEL` — локальный endpoint и имя модели
  (например, `http://127.0.0.1:8034/v1` и `qwen/qwen3-4b-2507`); модель
  должна быть загружена в LM Studio;
- `SEED_ON_START=true` — наполнить БД стартовым набором задач при запуске
  (идемпотентно; в Docker Compose включено по умолчанию).

> **Важно:** в `.env.example` порты `POSTGRES_PORT=5434` и `REDIS_PORT=6381`.
> Канонические 5432/6379 на машине разработки часто заняты другими проектами
> (см. `docs/KNOWN_ISSUES.md`, KI-001). Если они свободны — можно вернуть канон.

---

## 3. Поднять PostgreSQL и Redis (≈2 мин)

```bash
docker compose up -d postgres redis
docker compose ps
```

В колонке PORTS должно быть `127.0.0.1:5434->5432/tcp` и
`127.0.0.1:6381->6379/tcp`. Если порт «не опубликован» — он занят, см. KI-001.

---

## 4. Backend (≈5 мин)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1            # Linux: source venv/bin/activate
pip install -r requirements.txt

.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\alembic.exe check       # должно быть «No new upgrade operations detected»

.\venv\Scripts\python.exe scripts\seed_tasks.py   # 6 учебных задач
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Проверка: <http://127.0.0.1:8000/api/v1/health> →
`{"status":"ok","llm":{"provider":"deepseek","status":"not_configured",...},...}`
(статус `ok` появится после задания ключа или при `LLM_PROVIDER=echo`).
Сваггер: <http://127.0.0.1:8000/api/docs>

### Проверки качества

```powershell
.\venv\Scripts\ruff.exe check app tests
.\venv\Scripts\mypy.exe app --config-file ..\pyproject.toml
.\venv\Scripts\pytest.exe -q
```

> **PyPI с хоста может быть заблокирован** (KI-017). Тогда `pip install`/
> `pip-audit` локально не работают: аудит backend — в контейнере
> `python:3.12-slim`, локальный fallback — `backend/scripts/audit_python_deps.py`
> (см. [reports/sprint-20/SECURITY_AUDIT.md](reports/sprint-20/SECURITY_AUDIT.md)).

---

## 5. Frontend (≈5 мин)

```bash
cd frontend
pnpm install --allow-build=esbuild     # pnpm 12 требует явного разрешения
cp .env.example .env
pnpm dev
```

Откройте <http://127.0.0.1:3000>. Запросы к `/api` проксируются Vite на
`127.0.0.1:8000` — backend должен быть запущен.

Проверки:

```bash
pnpm typecheck && pnpm lint && pnpm test && pnpm build
pnpm test:offline                      # нет CDN-ссылок: Monaco локальный
```

---

## 6. Первый пользователь

1. Откройте <http://127.0.0.1:3000/register>, создайте аккаунт.
2. Роль всегда `student` — повышение только администратором.
3. Чтобы получить админа, выполните в БД:

```sql
UPDATE users SET role = 'admin' WHERE username = 'ваш_логин';
```

После этого в навигации появится раздел «Администрирование».

---

## 7. Docker-вариант (всё сразу)

```bash
docker compose up -d --build
```

- Frontend: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000/api/docs>

Production-конфиг (без публикации БД наружу):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Проверка после запуска: `GET /` отдаёт SPA, `curl -I http://127.0.0.1:3000/` —
все security-заголовки (CSP, `nosniff`, `DENY`, HSTS и др. — см.
[SPEC.md §6.1](SPEC.md#61-заголовки-безопасности-nginx-s20-002)); WS-чат
работает через nginx. Секреты (`POSTGRES_PASSWORD`, `SECRET_KEY`) обязательны —
compose не стартует с дефолтами (`:?`).

**Миграции применяются автоматически (S20-006).** Backend-контейнер запускает
`alembic upgrade head` в `docker-entrypoint.sh` до старта uvicorn, поэтому
чистая БД не даёт `UndefinedTableError`. Выкатить миграции отдельным job'ом
можно с `SKIP_MIGRATIONS=true` (см. `backend/docker-entrypoint.sh`).

---

## 8. Бэкап и восстановление БД (S20-004)

Скрипты работают через `docker exec` в контейнер `ai_teacher_postgres`,
поэтому локальный `pg_dump` не нужен. Запуск — из корня репозитория
в Git Bash / Linux / macOS (Windows: `bash scripts/backup.sh`).

```bash
# Бэкап: backups/<db>_<UTC>.dump.gz + .sha256, retention 14 дней
bash scripts/backup.sh

# Свои параметры
bash scripts/backup.sh -o /backups -r 30
```

Скрипт проверяет, что контейнер запущен (иначе дамп мог бы уйти в чужую БД —
KI-001), делает `pg_dump -Fc`, сжимает gzip, проверяет архив через
`pg_restore -l`, пишет sha256 и удаляет бэкапы старше retention.

Восстановление — **в отдельную БД**, рабочую `ai_teacher` скрипт перезапишет
только с `--force`:

```bash
# Smoke-проверка на scratch-БД: создать, восстановить, показать счётчики
bash scripts/restore.sh -f backups/ai_teacher_20261030T075746Z.dump.gz \
     -t ai_teacher_restore_check --create -y --verify

# Удалить scratch-БД после проверки
docker exec ai_teacher_postgres dropdb -U ai_teacher ai_teacher_restore_check
```

`restore.sh` требует подтверждения (`yes`) без `-y`, запрещает восстановление
в `postgres`/`template0`/`template1`, умеет `--create` (создать БД) и
`--clean` (очистить объекты перед восстановлением). Коды возврата: `0` —
успех, `1` — ошибка, `2` — отказ/неверные аргументы.

Проверено 2026-10-30: бэкап dev-БД, восстановление в
`ai_teacher_restore_check` — 14 таблиц, счётчики строк совпали с источником
(users=5, tasks=6, chat_sessions=2, chat_messages=2); retention удаляет
бэкапы старше N дней. Детали — `docs/reports/sprint-20/SECURITY_AUDIT.md`.

---

## Типичные проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| `password authentication failed for user "ai_teacher"` | занятый порт: контейнер не поднялся, подключение ушло в чужую БД | `docker compose ps`, сменить порт в `.env` (KI-001) |
| `extension "vector" is not available` | образ без pgvector | используется `pgvector/pgvector:pg17` (KI-003) |
| `ERR_PNPM_IGNORED_BUILDS` | pnpm 12 блокирует postinstall | `pnpm install --allow-build=esbuild` |
| `404` при заходе на `/tasks` в Docker | nginx без SPA-fallback | проверьте `frontend/nginx.conf` (`try_files`) |
| Чат отвечает 503 | не задан `DEEPSEEK_API_KEY` и LM Studio не запущен | задать ключ или `LLM_PROVIDER=lm_studio` |
| `alembic check` показывает расхождения | модели и миграции разошлись | `alembic revision --autogenerate`, проверить дифф |
| `restore.sh`: «рабочая БД. Используйте отдельную БД или --force» | защита от перезаписи `ai_teacher` | восстановить в scratch-БД (`-t ... --create`) |
| `.format()` в песочнице → `RestrictedFeatureError` | RestrictedPython 8.5 блокирует `str.format` (KI-018) | использовать f-строки `f"{x}"` или `%` |
| `pip install` падает с connection reset / timeout | PyPI с хоста заблокирован (KI-017) | ставить/аудитить через Docker; локальный аудит — `audit_python_deps.py` |


---

## Куда дальше

- [../docs/ARCHITECTURE.md](ARCHITECTURE.md) — как устроено
- [../docs/RULES.md](RULES.md) — правила разработки
- [../TODO_V0.2.md](../TODO_V0.2.md) — этап v0.2.0 (спринты 11–20, завершён)
- [../docs/KNOWN_ISSUES.md](KNOWN_ISSUES.md) — известные проблемы и принятые риски
