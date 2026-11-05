# Документация AI Teacher for Python

Навигационный хаб. Здесь собрано, что читать в зависимости от роли.

**Версия:** v0.3.3 (2026-11-05) · **Стек:** Python 3.12 + FastAPI · React 19 · PostgreSQL 17 + pgvector · Redis · Docker Compose

---

## С чего начать

| Если вы… | Начните с | Дальше |
|----------|-----------|--------|
| первый раз запускаете проект | [GETTING_STARTED.md](GETTING_STARTED.md) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| будете пользоваться как ученик | [USER_GUIDE.md](USER_GUIDE.md) | [ASSISTANT_LEVELS.md](ASSISTANT_LEVELS.md) |
| проверяете качество / приёмка | [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md) | [LLM_EVAL.md](LLM_EVAL.md) |
| пишете код в проекте | [RULES.md](RULES.md) | [ARCHITECTURE.md](ARCHITECTURE.md), [../TODO_V0.4.md](../TODO_V0.4.md) |
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
- [../TODO_V0.2.md](../TODO_V0.2.md) — завершённый этап v0.2.0 (спринты 11–20)
- [../TODO_V0.3.md](../TODO_V0.3.md) — завершённый этап v0.3.0 (спринты 21–30);
  патчи v0.3.1–v0.3.3 — в [RELEASES.md](RELEASES.md)
- [../TODO_V0.4.md](../TODO_V0.4.md) — **текущий этап v0.4.0** (спринты 33–41):
  детальный план задач `S33-001`…`S41-005`, зависимости, оценки, DoD и риски
- [CI.md](CI.md) — CI-платформа: self-hosted runner, гейты, релиз, эксплуатация
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
- [reports/](reports/) — отчёты по спринтам: [sprint-19](reports/sprint-19/SPRINT-19.md),
  [sprint-20](reports/sprint-20/SPRINT-20.md) (security-аудит — [SECURITY_AUDIT](reports/sprint-20/SECURITY_AUDIT.md))

---

## Текущее состояние

| Показатель | Значение |
|------------|----------|
| Версия | **v0.3.3** (2026-11-05); спринты 1–32 завершены, спринт 33 в работе |
| Тесты backend | **538** (516 passed + 22 skip в образе Python 3.12; локальный venv отстаёт — KI-017) |
| Тесты frontend | 94 unit + 12 e2e (Playwright; 12/12 green) |
| Покрытие | backend порог 70% (последний замер 80%), frontend 73.6% строк |
| Ruff / MyPy strict | 0 / 0 |
| Миграции | head 013 (`alembic check` чист) |
| Размер фронтенда | entry 78.71 kB gzip (лимит 80) |
| Зависимости | frontend 0 vulns; backend 0 critical (KI-015/KI-016 — принятые остатки) |
| Активные проблемы | 3 (см. [KNOWN_ISSUES.md](KNOWN_ISSUES.md)) |

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

# Эксплуатация (S20)
bash scripts/backup.sh                       # бэкап БД (docker exec pg_dump + gzip)
bash scripts/restore.sh -f <dump> -t <db> --create -y --verify
curl -I http://127.0.0.1:3000/               # security-заголовки nginx
```

---

© 2026 RuChating (iilmchat)
