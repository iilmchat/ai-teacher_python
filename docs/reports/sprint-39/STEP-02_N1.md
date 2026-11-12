# S39-002 — N+1 и индексы

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено

## Аудит

| Эндпоинт | Запросы | Вывод |
|----------|---------|-------|
| `GET /admin/users` | count + список | N+1 нет |
| `GET /admin/audit` | count + страница | N+1 нет |
| `GET /me/notifications` | user + deadline-join + список + unread | N+1 нет |
| `GET /admin/tasks/review` | очередь+агрегаты, recent-attempts, count | N+1 нет (3–4 запроса) |

`ModerationService.list_review_queue` уже использует CTE + оконную функцию
`row_number()` для последних попыток — не грузит попытки в цикле.

Новых индексов не добавляли: существующие (`idx_tasks_active_created`,
`idx_tasks_source_created`, `idx_audit_log_*`, `idx_notifications_*`,
`idx_progress_user`) покрывают фильтры/сортировки; подтверждённой
необходимости в миграции 023 нет.

## Регрессионные тесты

`backend/tests/test_query_counts.py` (4 теста): для каждого эндпоинта число
SELECT при 5 строках сравнивается с числом при 30–40 строках; рост означает
N+1 и валит тест. Используется SQLAlchemy event `before_cursor_execute`.

```
pytest tests/test_query_counts.py -q   # 4 passed
```
