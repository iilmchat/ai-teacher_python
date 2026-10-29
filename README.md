# AI Teacher for Python

Интерактивный ассистент-учитель по Python для школьников 10–17 лет.
Помогает **думать**, а не списывать: три уровня помощи, безопасная песочница кода
и задачи с автопроверкой.

**Версия:** v0.1.0 · **© 2026 RuChating (iilmchat)**

**Стек:** Python 3.12 + FastAPI · React 19 · PostgreSQL 17 + pgvector · Redis · DeepSeek / LM Studio · Docker Compose

---

## Возможности

- **Три уровня помощи** — базовый (наводящие вопросы, без готового кода),
  средний (объяснение + пример синтаксиса), продвинутый (полное решение с разбором).
- **Чат** со стримингом ответов (WebSocket) и REST-фолбэком.
- **Песочница кода** — RestrictedPython + изоляция процесса, белый список модулей,
  лимиты времени, памяти и вывода, ограничение параллельных запусков;
  линтер с ошибками безопасности и подсказками по стилю.
- **Задачи** — 6 готовых, проверка по тест-кейсам с `input()`, подсказки по одной,
  подробный отчёт; импорт/экспорт JSON/YAML, генерация через LLM, теги и версии.
- **Прогресс** — статусы, попытки, процент решения, разбивка по сложности.
- **Админка** — пользователи и роли, задачи, аналитика (DAU, попытки, сообщения, запуски).
- **Кабинет учителя** — CRUD задач с конструктором тест-кейсов, импорт файла,
  прогресс учеников.
- **Надёжность LLM** — healthcheck провайдера, fallback «облако → локально»,
  метрики латентности и токенов, детектор готовых решений на базовом уровне.
- **i18n** — русский и английский.

---

## Быстрый старт

```bash
git clone https://github.com/iilmchat/ai-teacher_python.git
cd ai-teacher_python
cp .env.example .env            # заполните SECRET_KEY, POSTGRES_PASSWORD, DEEPSEEK_API_KEY

docker compose up -d postgres redis

# Backend
cd backend
python -m venv venv && .\venv\Scripts\Activate.ps1   # Linux: source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_tasks.py
uvicorn app.main:app --reload --port 8000

# Frontend (в новом терминале)
cd frontend
pnpm install --allow-build=esbuild
pnpm dev
```

- Frontend: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000/api/v1/health> · Swagger: <http://127.0.0.1:8000/api/docs>

Подробно, с типичными ошибками — [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

---

## Статус

| Показатель | Значение |
|------------|----------|
| Спринты | 1–15 завершены (19 — частично; v0.2.0) |
| Тесты backend | **256** (pytest, реальный PostgreSQL; +1 skip на Windows) |
| Тесты frontend | **71** unit + **12** e2e (Playwright) |
| Покрытие | backend **82%**, frontend **73.6%** строк |
| Ruff / MyPy strict | 0 / 0 |
| TypeScript | strict, 0 ошибок |
| Размер фронтенда | entry **76 kB** gzip, initial ~110 kB |

---

## Документация

Навигация: [docs/README.md](docs/README.md)

- [docs/SPEC.md](docs/SPEC.md) — контракты API, схема БД, критерии приёмки
- [Design.md](Design.md) — исходный дизайн и решения
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — как устроено сейчас
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — инструкция ученику
- [docs/ASSISTANT_LEVELS.md](docs/ASSISTANT_LEVELS.md) — уровни помощи
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — развёртывание
- [docs/MANUAL_TESTING_GUIDE.md](docs/MANUAL_TESTING_GUIDE.md) — приёмка
- [docs/LLM_EVAL.md](docs/LLM_EVAL.md) — оценка качества ответов LLM
- [docs/DESIGN_ADMIN_AND_OPS.md](docs/DESIGN_ADMIN_AND_OPS.md) — админка, LLMOps, FinOps
- [docs/PROMPT_CURRENT.md](docs/PROMPT_CURRENT.md) — актуальные инструкции ассистента
- [docs/RULES.md](docs/RULES.md) — правила разработки
- [docs/RELEASES.md](docs/RELEASES.md) · [docs/CHANGELOG.md](docs/CHANGELOG.md) · [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)
- [TODO.md](TODO.md) — план работ

---

## Лицензия

MIT License · © 2026 RuChating (iilmchat)
