# Sprint 11: Quality Gates & E2E — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён (S11-008 — частично)

---

## 1. Файлы (+/-)

### Backend
```
+ app/db/redis.py                          — ленивый Redis-клиент, ping, close
+ app/services/llm/echo.py                 — детерминированный провайдер для e2e
+ scripts/check_ports.py                   — проверка портов и «своей» БД
+ scripts/prepare_e2e_db.py                — создание БД для e2e
+ tests/test_rate_limit.py                 — 10 тестов
+ tests/test_websocket_stream.py           — 5 тестов
+ tests/test_migrations.py                 — 4 теста
~ app/core/rate_limiter.py                 — RateLimitMiddleware (fail-open)
~ app/main.py                              — middleware, lifespan с Redis
~ app/api/websocket.py                     — serve_chat_socket + Depends
~ app/config.py                            — rate_limit_enabled
~ app/services/llm/__init__.py             — провайдер echo
~ tests/conftest.py                        — отключение лимитов в тестах
```

### Frontend
```
+ playwright.config.ts                     — два webServer, отдельная БД, echo
+ e2e/helpers.ts
+ e2e/auth.spec.ts                         — 4 сценария
+ e2e/chat.spec.ts                         — 2 сценария
+ e2e/playground.spec.ts                   — 3 сценария
+ e2e/tasks.spec.ts                        — 3 сценария
~ src/App.tsx                              — loadMe() при старте (исправление бага)
~ src/components/code-editor/CodeEditor.tsx — textarea при VITE_E2E=1
~ vite.config.ts                           — порт/прокси из env, coverage-пороги
~ package.json                             — e2e, test:coverage, Playwright
~ src/vite-env.d.ts                        — VITE_E2E
```

### Инфраструктура и документы
```
~ .github/workflows/ci.yml                 — job e2e, coverage
~ pyproject.toml                           — маркеры, fail_under=70
~ docs/KNOWN_ISSUES.md, RELEASES.md, CHANGELOG.md, RULES.md, README.md
+ docs/reports/sprint-11/SPRINT-11.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 137 | **156** (+19) |
| Frontend unit | 63 | 63 |
| Frontend e2e | 0 | **12** |
| Backend покрытие | не измерялось | **81%** (порог 70) |
| Frontend покрытие (`lib`, `store`) | — | 74% строк, 78% ветвей |

Новые тесты:

- `test_rate_limit.py` — 10: счётчик, 429, `Retry-After`, health exempt,
  отключение флагом, fail-open (2 варианта), `X-Forwarded-For`
- `test_websocket_stream.py` — 5: полный стриминг с сохранением в БД, ping/pong,
  не-JSON, неизвестный тип, ошибка провайдера
- `test_migrations.py` — 4: upgrade на пустую БД, сверка колонок,
  downgrade → upgrade, единственная голова

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest -q` | **156 passed** за 59 с |
| Покрытие backend | `pytest --cov=app` | **81%** |
| Ruff / MyPy | `ruff check app tests scripts`, `mypy app` | 0 / 0 |
| Миграции | `pytest tests/test_migrations.py` | 4 passed |
| Frontend типы/линт | `pnpm typecheck && pnpm lint` | 0 / 0 |
| Frontend unit | `pnpm test` | 63 passed |
| Frontend coverage | `pnpm test:coverage` | 74/78/84% |
| E2E | `pnpm e2e` | **12 passed** за 30 с |
| Проверка портов | `python scripts/check_ports.py --docker` | все OK |

---

## 4. Smoke

```
python scripts/check_ports.py --docker
  [OK] postgres 127.0.0.1:5434, таблиц: 7
  [OK] redis   127.0.0.1:6381 PONG
  [OK] docker  контейнеры публикуют ожидаемые порты

pnpm e2e (12 сценариев):
  auth: регистрация/вход/выход, защита, неверный пароль, отказ в админку
  chat: стриминг «● live» + ответ по уровню
  playground: вывод 10, блокировка os, ZeroDivisionError
  tasks: каталог, решение 3/3, подсказки по одной
  → 12 passed
```

---

## 5. Что не так

1. **S11-008 частично:** xdist (`-n auto`) не добавлен — при 59 с полного
   прогона выигрыш не оправдывает зависимость.
2. В e2e редактор заменён textarea (`VITE_E2E=1`), поэтому Monaco в браузере
   не проверяется — это остаётся в KI-013 (спринт 19).
3. Смена роли админом через UI не покрыта e2e: в e2e-БД нет администратора
   (появляется в спринте 15 вместе с Teacher Console).
4. `check_ports.py --docker` зависит от Docker CLI; без него — предупреждение.

---

## 6. Новые KI

Новых проблем не заведено. Закрыто 5: KI-001, KI-002, KI-006, KI-007, KI-012.
Активными остались: KI-008, KI-009, KI-010, KI-013.

---

## 7. Обоснование

- **Отдельная БД и порт для e2e.** Тесты не мешают разработке (8000/3000) и
  не засоряют рабочую БД; `prepare_e2e_db.py` создаёт базу при первом прогоне.
- **Провайдер `echo`.** Детерминированные ответы по уровню позволяют проверять
  UI-поток чата без ключа и без сети; в проде он не используется.
- **Textarea в e2e.** Зависимость от CDN Monaco сделала бы тесты нестабильными;
  логика страниц проверяется одинаково, а редактор — отдельно (KI-013).
- **In-memory фейк Redis в тестах лимитов.** RULES требует изоляции: реальный
  Redis между event loop'ами давал `Event loop is closed`. Middleware при этом
  проверяется целиком, включая fail-open.
- **Вынос WS-протокола в функцию.** Позволил покрыть стриминг без реального
  сокета и `TestClient` (который конфликтует с async-фикстурой БД).
- **Маркеры `slow`/`migrations`.** Полный прогон остаётся быстрым (~59 с), а
  тяжёлые тесты можно запускать отдельно.
- **Побочная ценность e2e.** Сразу нашёлся реальный баг: после F5 защищённые
  страницы показывали вечный Spinner — исправлен в `App.tsx`.

---

**Дата:** 2026-10-29
