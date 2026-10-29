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

---

## Куда дальше

- [../docs/ARCHITECTURE.md](ARCHITECTURE.md) — как устроено
- [../docs/RULES.md](RULES.md) — правила разработки
- [../TODO.md](../TODO.md) — что дальше по плану
