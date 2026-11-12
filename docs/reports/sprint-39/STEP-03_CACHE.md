# S39-003 — кэширование и инвалидация

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено

## Что добавлено

`GET /admin/quality` — тяжёлые агрегаты по `message_feedback`/чатам:
счётчики, срезы провайдер/модель/уровень, проблемные темы, негативные
примеры. Добавлен кэш:

- ключ `cache:admin:quality`, TTL **60 c**;
- `cache_get_json` → `AdminQualityResponse.model_validate`;
- `cache_set_json(..., ttl=60)`;
- инвалидация `invalidate_quality_cache()` при `set_feedback`/`remove_feedback`
  (`FeedbackService`).

Свежесть: админский экран допускает задержку до минуты, но изменение оценки
сбрасывает кэш сразу. `GET /tasks/recommended` **не** кэшировали: результат
зависит от прогресса и меняется после submit; TTL 60 c дал бы ложные
рекомендации.

## Метрики

`cache_hits_total`/`cache_misses_total` и hit-rate в `/admin/analytics` уже
есть (S19/S35), отдельный алерт не добавляли; смотреть на дашборде.

## Проверки

```
pytest tests/test_cache.py -q   # 11 passed
```

Новые тесты: `test_admin_quality_is_cached_on_second_request` (первый set,
второй hit, TTL 60), `test_quality_cache_is_invalidated`.
