# Sprint 4: Chat Service — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён (два пункта частично)

---

## 1. Файлы (+/-)

### Созданные
```
+ backend/app/errors.py                              — доменные исключения
+ backend/app/services/llm/base.py                   — контракт LLMProvider
+ backend/app/services/llm/deepseek.py               — провайдер DeepSeek
+ backend/app/services/llm/lm_studio.py              — провайдер LM Studio
+ backend/app/services/llm/__init__.py               — фабрика провайдеров
+ backend/app/services/llm/prompt_builder.py         — сборка сообщений
+ backend/app/services/llm/prompts/basic.txt
+ backend/app/services/llm/prompts/intermediate.txt
+ backend/app/services/llm/prompts/advanced.txt
+ backend/app/services/chat_service.py               — логика чата
+ backend/app/api/v1/chat.py                         — REST чата
+ backend/app/api/websocket.py                       — WS-стриминг
+ backend/tests/test_chat.py                         — 13 тестов
+ backend/tests/test_prompts.py                      — 21 тест
+ backend/tests/test_websocket.py                    — 2 теста
```

### Изменённые
```
~ backend/app/schemas/chat.py   — ChatMessageRequest, ChatTurnResponse
~ backend/app/main.py           — chat/ws роутеры, обработчик AppError
```

---

## 2. Покрытие

| Файл | Тестов | Что проверяет |
|------|--------|----------------|
| `test_chat.py` | 13 | сессии, сообщения, 403/404, контекст, извлечение кода |
| `test_prompts.py` | 21 | промпты уровней, сборка контекста, фабрика провайдеров |
| `test_websocket.py` | 2 | авторизация WS |
| **Итого** | **36** новых, **53** всего | |

Ключевые проверки:
- системный промпт выбранного уровня действительно уходит в LLM;
- история предыдущего обмена попадает в контекст, текущий вопрос не дублируется;
- чужую сессию нельзя прочитать, дополнить или удалить (403);
- блоки кода из markdown извлекаются в `code_blocks`;
- пустое и пробельное сообщение отклоняются (422).

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Линтер | `ruff check app tests` | `All checks passed!` |
| Типы | `mypy app --config-file ../pyproject.toml` | `Success: no issues found in 32 source files` |
| Тесты | `pytest -q` | `53 passed in 24.33s` |
| Миграции | `alembic check` | расхождений нет |
| OpenAPI | `GET /api/openapi.json` | 9 путей, включая chat |

---

## 4. Smoke

```
GET  /api/v1/health → {"status":"ok","version":"0.1.0","llm_provider":"deepseek"}
GET  /api/v1/chat/sessions (без токена) → 403
GET  /api/v1/chat/sessions (с токеном) → 200 [] (в тестах)
WS   /api/v1/chat/ws/{id} (без токена) → {"type":"error","detail":"Требуется авторизация"}
```

Реальный стриминг требует API-ключа DeepSeek или запущенного LM Studio,
поэтому проверялся через фейковый провайдер в тестах.

---

## 5. Что не так

1. **KI-006:** полный WS-сценарий не покрыт автотестом (только отказ авторизации).
2. **KI-007:** rate limiting по-прежнему не подключён к приложению.
3. **Реальные вызовы LLM не проверены** — нет ключа DeepSeek/LM Studio;
   провайдеры покрыты тестами только на уровне фабрики.
4. **Версионирование промптов** ограничено git-историей файлов.

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-006 | Open | Low | Нет интеграционного теста WS-стриминга |
| KI-007 | Open | Med | Rate limiting middleware не подключён |

---

## 7. Обоснование

- **Провайдер за интерфейсом.** `LLMProvider` отделяет транспорт от
  образовательной логики: тесты подменяют провайдер, продакшен выбирает
  DeepSeek или LM Studio через `LLM_PROVIDER`.
- **Промпты в файлах.** RULES §8.1 требует версионировать инструкции отдельно
  от кода: изменение текста видно в диффе и покрыто тестами на маркеры.
- **Уровень хранится в сессии.** Пользователь может вести параллельные диалоги
  с разным уровнем помощи; при создании сессии уровень наследуется от профиля.
- **История обрезается до 20 сообщений и 4000 символов.** Ограничивает
  стоимость и латентность, сохраняя связность диалога.
- **JWT в query-параметре для WS.** Браузерный WebSocket не позволяет задать
  заголовок `Authorization`; токен проверяется тем же `decode_token`.
- **`AppError` вместо HTTPException в сервисах.** Сервисы не зависят от FastAPI,
  а коды ответов задаются в одном месте.
- **Сохранение ответа после завершения потока.** Позволяет не терять диалог
  при обрыве соединения и корректно записывать `code_blocks`.

---

**Дата:** 2026-10-29
