# Документация AI Teacher for Python

Навигационный хаб. Здесь собрано, что читать в зависимости от роли.

**Версия:** v0.1.0 · **Стек:** Python 3.12 + FastAPI · React 19 · PostgreSQL 17 + pgvector · Redis · Docker Compose

---

## С чего начать

| Если вы… | Начните с | Дальше |
|----------|-----------|--------|
| первый раз запускаете проект | [GETTING_STARTED.md](GETTING_STARTED.md) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| будете пользоваться как ученик | [USER_GUIDE.md](USER_GUIDE.md) | [ASSISTANT_LEVELS.md](ASSISTANT_LEVELS.md) |
| проверяете качество / приёмка | [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md) | [LLM_EVAL.md](LLM_EVAL.md) |
| пишете код в проекте | [RULES.md](RULES.md) | [ARCHITECTURE.md](ARCHITECTURE.md), [../TODO.md](../TODO.md) |
| администрируете и эксплуатируете | [DESIGN_ADMIN_AND_OPS.md](DESIGN_ADMIN_AND_OPS.md) | [RELEASES.md](RELEASES.md) |
| работаете с ассистентом (LLM) | [PROMPT_CURRENT.md](PROMPT_CURRENT.md) | [LLM_EVAL.md](LLM_EVAL.md) |
| готовите релиз | [RELEASES.md](RELEASES.md) | [CHANGELOG.md](CHANGELOG.md) |

---

## Карта документов

### Для пользователей

- [USER_GUIDE.md](USER_GUIDE.md) — сценарий работы: чат, песочница, задачи, прогресс, профиль
- [ASSISTANT_LEVELS.md](ASSISTANT_LEVELS.md) — чем отличаются три уровня помощи

### Для разработчиков

- [SPEC.md](SPEC.md) — контракты: API, схема БД, статусы, критерии приёмки
- [../Design.md](../Design.md) — архитектура и принятые решения (исходный документ)
- [ARCHITECTURE.md](ARCHITECTURE.md) — как система устроена сейчас: модули, потоки, контракты
- [RULES.md](RULES.md) — правила кода, тестов, коммитов, окружения
- [../TODO.md](../TODO.md) — завершённый этап v0.1.0 (спринты 1–10)
- [../TODO_V0.2.md](../TODO_V0.2.md) — **план этапа v0.2.0** (спринты 11–20; 11–16 закрыты, 19 — частично)
- [GETTING_STARTED.md](GETTING_STARTED.md) — развёртывание за ~20 минут

### Для QA и продукта

- [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md) — ручные кейсы и чек-лист приёмки
- [LLM_EVAL.md](LLM_EVAL.md) — оценка качества ответов LLM-as-judge и её ограничения

### Для эксплуатации и LLMOps

- [DESIGN_ADMIN_AND_OPS.md](DESIGN_ADMIN_AND_OPS.md) — админка, мониторинг, FinOps, guardrails
- [PROMPT_CURRENT.md](PROMPT_CURRENT.md) — актуальные системные инструкции ассистента и метрики

### История и проблемы

- [RELEASES.md](RELEASES.md) — журнал спринтов и релизов
- [CHANGELOG.md](CHANGELOG.md) — история изменений (Keep a Changelog)
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — реестр известных проблем (`KI-NNN`)
- [reports/](reports/) — отчёты по спринтам

---

## Текущее состояние

| Показатель | Значение |
|------------|----------|
| Спринты | 1–16 завершены (19 — частично) |
| Тесты backend | 264 (pytest, реальный PostgreSQL; +1 skip на Windows) |
| Тесты frontend | 74 unit + 12 e2e (Playwright) |
| Покрытие | backend 80%, frontend 73.6% строк |
| Ruff / MyPy strict | 0 / 0 |
| Размер фронтенда | entry 77 kB gzip, initial ~111 kB |
| Открытые проблемы | 1 (см. [KNOWN_ISSUES.md](KNOWN_ISSUES.md)) |

---

## Быстрые ссылки

```bash
# Backend
cd backend && .\venv\Scripts\pytest.exe -q
.\venv\Scripts\pytest.exe -q -m "not slow and not migrations"   # быстрый прогон
.\venv\Scripts\ruff.exe check app tests scripts
.\venv\Scripts\mypy.exe app --config-file ../pyproject.toml
.\venv\Scripts\alembic.exe upgrade head && .\venv\Scripts\alembic.exe check
.\venv\Scripts\python.exe scripts\check_ports.py --docker

# Frontend
cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build
pnpm test:coverage
pnpm e2e            # Playwright: backend на 8001 + vite на 3100

# Стек
docker compose up -d postgres redis
```

---

© 2026 RuChating (iilmchat)
