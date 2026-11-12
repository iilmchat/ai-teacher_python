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

### Если PyPI недоступен: wheelhouse (S22-005)

PyPI с рабочей машины может быть заблокирован (KI-017). Тогда зависимости
ставятся из локального «склада» колёс:

```powershell
# 1) скачать все пины (Docker, Linux-колёса — как в CI):
python scripts/wheelhouse.py build --out .wheelhouse --docker `
    --index-url https://mirrors.aliyun.com/pypi/simple/

# 2) поставить в venv без сети:
python scripts/wheelhouse.py install --from .wheelhouse `
    --python backend\venv\Scripts\python.exe

# 3) посмотреть, что лежит:
python scripts/wheelhouse.py list --from .wheelhouse
```

`.wheelhouse/` — в `.gitignore`; колёса, собранные pip'ом Windows-хоста, в
Linux-контейнер не ставятся, поэтому в CI используется тот же скрипт, но с
именованным томом (`scripts/ci/build-wheelhouse.ps1`). Порядок безопасного
апгрейда зависимостей — [RULES.md](RULES.md) §11.21.

> Аудит backend — в контейнере `python:3.12-slim` (`pip-audit`), локальный
> fallback — `backend/scripts/audit_python_deps.py`
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

Production-конфиг (образы из GHCR, Caddy + TLS):

```bash
cp .env.prod.example .env.prod
$EDITOR .env.prod                 # DOMAIN, SECRET_KEY, POSTGRES_PASSWORD

docker login ghcr.io -u <github-user> --password-stdin
bash scripts/pin_images.sh --tag v0.6.0   # зафиксировать digest в .env.prod
bash scripts/deploy.sh                    # бэкап → миграции → up → health
```

- Публичный вход — только **Caddy** (`https://<DOMAIN>`), он же проксирует
  `/api/*` и WebSocket чата. `frontend:80` и `backend:8000` наружу не
  публикуются.
- Пилот на общем VPS: `CADDY_HTTP_PORT=8080`, `CADDY_HTTPS_PORT=8443`
  (внешний reverse-proxy проксирует на них).
- `deploy.sh` делает бэкап, применяет `alembic upgrade head` отдельным
  контейнером `migrate`, поднимает `backend/frontend/caddy`, проверяет
  `/health/ready` и при провале откатывается на `.last_deploy`.
- Ручной запуск без скрипта:
  ```bash
  docker compose --env-file .env.prod -f docker-compose.prod.yml \
    --profile tools run --rm migrate
  docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
  ```
- Миграции больше не применяются в entrypoint backend
  (`SKIP_MIGRATIONS=true`): их выполняет `migrate`. Если поднимаете стек
  вручную, не забудьте про `migrate`.
- Проверка: `curl -fsS https://<DOMAIN>/` (SPA), `/api/v1/health`, WebSocket
  чата. TLS-сертификат Caddy получает автоматически (ACME).
- Домен/порты/бэкапы/откат — `docs/RUNBOOK.md`; секреты — `SECURITY.md`.

**Миграции применяются автоматически (S20-006) в dev-стеке.** В prod —
отдельным one-shot контейнером `migrate` (S36-004), см. выше.

---

## 8. Бэкап, шифрование и восстановление (S36)

`scripts/backup.sh` сам находит контейнер БД через `docker compose ps`
(имя не хардкодится), делает `pg_dump -Fc`, проверяет архив, сжимает gzip,
опционально шифрует `age` и выгружает в Selectel S3. Ежедневный запуск —
systemd `ai-teacher-backup.timer` (03:00 UTC).

```bash
# Локально: backups/<db>_<UTC>.dump.gz[.age] + .sha256, retention 14 дней
bash scripts/backup.sh

# С шифрованием и S3 (ключи в ENV или /etc/ai-teacher/backup.env)
AGE_RECIPIENT=age1... S3_BUCKET=... bash scripts/backup.sh

# Восстановление в scratch-БД (безопасно): --create -y --verify
bash scripts/restore.sh -f backups/ai_teacher_<stamp>.dump.gz \
     -t ai_teacher_restore_check --create -y --verify

# Автоматический DR-drill: последний бэкап → scratch → проверки → удаление
bash scripts/restore_drill.sh
```

Для `*.age`: `--age-identity /etc/ai-teacher/age.key` (или ENV
`AGE_IDENTITY`). Рабочая БД перезаписывается только с `--force`; системные
БД (`postgres`, `template0/1`) запрещены. Метрика
`backup_last_success_timestamp` уходит в node-exporter для алерта
`BackupStale`.

Установка systemd-таймера:

```bash
sudo install -d -m 0750 /etc/ai-teacher
sudo install -m 0600 deploy/systemd/backup.env.example /etc/ai-teacher/backup.env
sudo editor /etc/ai-teacher/backup.env
sudo cp deploy/systemd/ai-teacher-backup.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ai-teacher-backup.timer
```

Подробные процедуры — `docs/RUNBOOK.md` §5.

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

> **Сборка образов без PyPI (S25).** `backend/Dockerfile` и
> `backend/sandbox_runner/Dockerfile` принимают `--build-arg PIP_INDEX_URL`;
> `scripts/ci/docker.ps1` передаёт зеркало (`CI_PYPI_MIRROR`, по умолчанию
> `mirrors.aliyun.com`), иначе сборка висит на pypi.org. GitHub-hosted runner
> может использовать индекс по умолчанию.
