# SPRINT-27.md — RAG v2 & Search UX (v0.3.0)

**Период:** 2026-11-01  
**Задачи:** S27-001…S27-004  
**Статус:** ✅ backfill, порог, UI поиска, фикстуры качества, документация

---

## 1. Файлы (+/-)

```
+ backend/app/services/backfill.py            — идемпотентный backfill
+ backend/scripts/backfill_embeddings.py      — CLI (--dry-run/--limit/--sleep)
+ backend/tests/test_rag_backfill.py           — 8 тестов
+ backend/tests/fixtures/rag_queries.json      — запросы/ожидаемые сообщения
+ frontend/src/components/chat/ChatSearchPanel.tsx
+ frontend/src/test/chat-search.test.tsx       — 4 теста
+ docs/reports/sprint-27/SPRINT-27.md
~ backend/app/services/rag.py                  — RAG_MIN_SCORE
~ backend/app/config.py                        — rag_min_score
~ frontend/src/pages/ChatPage.tsx              — панель поиска
~ frontend/src/types/api.ts                    — ChatSearch*
~ frontend/src/i18n/locales/{ru,en}.json       — chat.search.*
~ frontend/e2e/chat.spec.ts                    — e2e-сценарий поиска
~ docs: SPEC §17, USER_GUIDE, ARCHITECTURE, RULES §11.24, CHANGELOG, RELEASES,
  TODO, backend/.env.example
```

---

## 2. Покрытие

Backend (8): backfill заполняет пропуски; повторный запуск ничего не делает;
dry-run не пишет; ошибка провайдера не рвёт прогон; `--limit` останавливает;
порог отбрасывает слабые попадания и уходит в fallback; `RAG_MIN_SCORE=0`
сохраняет прежнее поведение; precision@k на фикстурах = 1.0.

Frontend (4): результаты с `<mark>` и переходом к сессии; пустое состояние;
ошибка с `role="alert"`; `aria-live` во время загрузки. Плюс e2e: «ищет по
истории чата и открывает сессию».

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | 0 |
| `mypy app` (strict) | 0 |
| Backend | **492 passed + 1 skipped** |
| Frontend | **84 passed** (`typecheck`/`lint` — 0) |
| Миграции | не требовались |

---

## 4. Smoke

1. `python backend/scripts/backfill_embeddings.py --dry-run` → сводка
   `scanned/updated/remaining`, записи не меняются.
2. Повторный запуск без `--dry-run` → `remaining=0`, второй прогон `scanned=0`.
3. `RAG_MIN_SCORE=0.5`, запрос «собака» → semantic; ослабить порог до 0.99 →
   fallback `ilike` и предупреждение в логе.
4. В UI: «Поиск по чату» → «Найти» → подсветка, клик открывает сессию.

---

## 5. Что не так

1. **Семантика в e2e не проверяется** — в CI RAG выключен; e2e покрывает
   ILIKE-режим и UI. Семантика — unit-тесты на фейковых эмбеддингах.
2. **Backfill не автоматизирован** — ручной запуск/по cron; провайдер
   эмбеддингов в dev может быть недоступен (скрипт выходит с кодом 2).
3. **Порог не адаптивный** — единое значение `RAG_MIN_SCORE`; подбор под данные
   (например, по precision@k) — задача эксплуатации.

---

## 6. Новые KI

Нет.

---

## 7. Обоснование

1. **Исключение обработанных id.** Первая версия цикла на dry-run/ошибках
   зацикливалась (сообщение остаётся без эмбеддинга) — `notin_(seen)` решает
   проблему и сохраняет идемпотентность.
2. **Порог до fallback.** Слабые семантические попадания хуже, чем честный
   ILIKE; фильтр + fallback дают предсказуемый результат.
3. **Фикстуры вместо «на глаз».** Precision@k на детерминированных векторах
   ловит регрессии порога/выдачи без сети.
4. **Поиск по submit, не по вводу.** Один запрос на действие, меньше нагрузки и
   понятное поведение для скринридера (`aria-live`).
