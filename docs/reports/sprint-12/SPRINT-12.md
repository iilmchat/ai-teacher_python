# Sprint 12: LLMOps — Отчёт

**Период:** 2026-10-29
**Статус:** ⚠️ Частично (S12-004 — KI-008 Blocked: нет ключа/LM Studio)

---

## 1. Файлы (+/-)

### Backend
```
+ app/services/llm/health.py               — статус провайдера + кэш 60 с
+ app/services/llm/fallback.py             — FallbackProvider, 503 при отказе обоих
+ app/services/llm/metrics.py              — LLMMetrics + MetricsProvider
+ app/services/llm/policy.py               — детектор готового решения для basic
+ app/services/llm/eval_runner.py          — прогон Q1–Q5 × 3 уровня
+ app/services/llm/prompts/versions.json   — версии промптов
+ scripts/run_llm_eval.py                  — CLI прогона LLM_EVAL
+ alembic/versions/20261029_0004_chat_message_metadata.py
+ tests/test_llm_health.py                 — 9 тестов
+ tests/test_llm_fallback.py               — 7 тестов
+ tests/test_llm_metrics.py                — 6 тестов
+ tests/test_llm_policy.py                 — 8 тестов
+ tests/test_llm_eval_runner.py            — 4 теста
~ app/services/llm/base.py                 — LLMUsage, is_configured, ping, used_provider
~ app/services/llm/deepseek.py             — usage, ping, stream_options
~ app/services/llm/lm_studio.py            — usage, ping
~ app/services/llm/echo.py                 — model=echo
~ app/services/llm/__init__.py             — фабрика: metrics + fallback
~ app/services/llm/prompt_builder.py       — versions.json, prompt_version()
~ app/services/chat_service.py             — метаданные ответа, warnings
~ app/services/llm/__init__.py, app/config.py — LLM_FALLBACK_PROVIDER
~ app/api/v1/chat.py                       — явная сборка ответа с метаданными
~ app/api/v1/admin.py                      — секция llm в аналитике
~ app/api/websocket.py                     — warnings в done
~ app/main.py                              — health.llm, обработчик 503
~ app/models/chat.py                       — message_metadata JSONB
~ app/db/repositories/chat.py              — metadata при создании
~ app/schemas/chat.py, app/schemas/admin.py — metadata/warnings, AnalyticsLLM
~ tests/test_chat.py, test_admin.py, test_prompts.py, test_websocket_stream.py
```

### Frontend
```
~ src/types/api.ts                         — metadata/warnings, health.llm, analytics.llm
~ src/pages/AdminPage.tsx                  — карточка «Ассистент за 24 часа»
~ src/components/chat/MessageList.tsx      — плашка нарушения политики
~ src/lib/chatSocket.ts                    — warnings из done
~ src/hooks/useChatSession.ts              — прокидывание warnings
~ src/store/chat.ts                        — finishStream(full, warnings)
~ src/i18n/locales/ru.json, en.json        — новые строки
~ src/test/chat-components.test.tsx, chat-store.test.ts
```

### Документы
```
+ docs/reports/sprint-12/SPRINT-12.md
~ docs/RELEASES.md, CHANGELOG.md, KNOWN_ISSUES.md, RULES.md (§11.13),
  PROMPT_CURRENT.md, LLM_EVAL.md, DESIGN_ADMIN_AND_OPS.md, SPEC.md,
  MANUAL_TESTING_GUIDE.md, TODO_V0.2.md, README.md, docs/README.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 156 | **200** (+44) |
| Frontend unit | 63 | **65** (+2) |
| Backend покрытие | 81% | **83%** (порог 70) |

Новые тесты:

- `test_llm_health.py` — 9: `ok`/`degraded`/`not_configured`, кэш и TTL,
  endpoint без ключа (ключ не раскрыт), echo, fallback в health
- `test_llm_fallback.py` — 7: fallback в generate/stream, обрыв после первого
  токена, usage фактического провайдера, 503 в API
- `test_llm_metrics.py` — 6: токены, ошибки, первый токен, агрегация по
  провайдерам, окна час/сутки, reset
- `test_llm_policy.py` — 8: короткий синтаксис, длинный блок, полная программа,
  фразы, другие уровни
- `test_llm_eval_runner.py` — 4: 15 файлов + SUMMARY, версии промптов, каталог,
  статус провайдера
- Дополнены: чат (+4), админка (секция llm), промпты (+4), WS (+1)

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest -q` | **200 passed** за ~105 с |
| Покрытие backend | `pytest --cov=app` | **83%** (порог 70) |
| Ruff / MyPy | `ruff check app tests scripts`, `mypy app` | 0 / 0 |
| Миграции | `alembic upgrade head`, `alembic check` | без расхождений |
| Frontend typecheck | `pnpm typecheck` | 0 ошибок |
| Frontend lint | `pnpm lint` | 0 ошибок |
| Frontend unit | `pnpm test` | **65 passed** |
| Frontend build | `pnpm build` | 119.88 kB gzip |
| LLM_EVAL smoke | `run_llm_eval.py --provider echo` | 15 ответов, exit 0 |

---

## 4. Smoke

1. **Health без ключа.** `GET /api/v1/health` → `llm.status = not_configured`,
   `configured=false`, ключ в ответе отсутствует.
2. **Health с echo.** `LLM_PROVIDER=echo` → `llm.status = ok`, `model=echo`,
   ответ укладывается в кэш (повторный вызов не пингует).
3. **Fallback.** Основной провайдер-фейк падает → отвечает резервный,
   в логах `llm_fallback_used`, счётчик `fallback_used` растёт; оба падают →
   `POST /chat/sessions/{id}/messages` возвращает 503 с понятным текстом.
4. **Политика уровня.** `basic` + ответ с полной программой → `warnings:
   ["basic_full_solution"]` в REST и в WS `done`; в UI — плашка; `advanced`
   с тем же ответом — без предупреждений.
5. **Метаданные.** `GET /chat/sessions/{id}` → у ответа есть
   `metadata.provider`, `metadata.model`, `metadata.prompt_version=1`.
6. **Админка.** После вызовов LLM карточка «Ассистент за 24 часа» показывает
   запросы, ошибки, латентность, токены, fallback.
7. **LLM_EVAL.** `python scripts/run_llm_eval.py --provider echo --out <tmp>` →
   15 файлов + `SUMMARY.md` + `results.json`; без ключа (`--provider deepseek`)
   скрипт завершается с кодом 2 и не пишет мусор.

---

## 5. Что не так

- **Живой прогон LLM_EVAL не выполнен:** нет `DEEPSEEK_API_KEY`, LM Studio не
  запущен. KI-008 переведён в Blocked; инструмент и процедура готовы, при
  появлении ключа остаётся один запуск и ручная оценка.
- Метрики хранятся в памяти процесса и обнуляются при рестарте; экспорт в
  Prometheus/OTel — после v0.2.0.
- Healthcheck пингует провайдера раз в 60 с; при «холодном» запросе
  `/health` может отвечать до 5 с (DeepSeek) / 3 с (LM Studio).
- Политика уровня — эвристика: возможны ложные срабатывания на длинных
  иллюстрациях синтаксиса; ответ не блокируется, поэтому риск ограничен
  шумом в метриках.
- Параллельный запуск двух pytest-процессов ломает общую тестовую БД —
  зафиксировано в RULES §11.13.
- **CI не стартовал (KI-014):** GitHub Actions падает за 2 с из-за
  лимита/платежа аккаунта; PR открыт, локальные проверки зелёные.

---

## 6. Новые KI

**KI-014 · Open · High · CI** — GitHub Actions не запускает job'ы: аккаунт
исчерпал лимит/платёж, job'ы падают за 2 с без шагов. Код и workflow ни при
чём, локальные проверки зелёные. План: Billing & plans → перезапуск CI.

Обновлён **KI-008**: `Open` → `Blocked` (нет ключа/LM Studio), описан
выполненный объём и точная процедура закрытия.

---

## 7. Обоснование

- **Healthcheck через `models.list()`.** Дешёвый вызов без генерации токенов;
  кэш 60 с защищает API провайдера от мониторинга каждые несколько секунд.
  `not_configured` отделён от `degraded` — иначе health врёт «ok» без ключа.
- **Fallback — декоратор провайдера, а не ветвление в чате.** `ChatService`
  не знает о резерве; политика «один повтор» живёт в одном месте и
  покрывается unit-тестами. В стриме fallback допустим только до первого
  токена: иначе ученик увидит склейку двух ответов.
- **Метрики — обёртка `MetricsProvider`.** Тот же приём, что и fallback:
  сервис чата не меняется, а метрика снимается на границе транспорта.
  `usage` берётся из ответа провайдера; DeepSeek отдаёт его в последнем чанке
  (`stream_options.include_usage`).
- **Метаданные ответа — JSONB-колонка, а не отдельная таблица.** Один ответ —
  один набор метаданных; JSONB не требует join и допускает аддитивные поля
  без миграции на каждое. Версия промпта хранится рядом с ответом, чтобы
  разбирать инциденты постфактум.
- **Политика уровня — предупреждение, а не блокировка.** Блокировка ухудшила
  бы опыт ученика (ответ уже сгенерирован и оплачен), а метрика и плашка
  дают сигнал преподавателю; детектор намеренно простой и проверяемый.
- **Инструмент LLM_EVAL в репозитории.** Ручной прогон из документации
  воспроизводится одной командой, а smoke на `echo` проверяет сам конвейер
  без ключа — это позволяет закрыть KI-008 сразу, как появится доступ.
