# S39-004 — лимиты тела, загрузок и таймауты

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено

## Edge и таймауты

Caddy (`deploy/caddy/Caddyfile`):

- `request_body { max_size 10MB }`;
- backend: `flush_interval -1` (LLM-стрим), `dial_timeout 5s`,
  `response_header_timeout 60s`, `read_timeout 600s`, `write_timeout 60s`;
- frontend: dial 5s, response header 30s.

nginx (`frontend/nginx.conf`):

- `client_max_body_size 10m`;
- `proxy_connect_timeout 5s`, `proxy_send_timeout 60s`,
  `proxy_read_timeout 3600s` (WebSocket/LLM).

## UploadFile

`POST /tasks/import/file`:

- `MAX_UPLOAD_BYTES` (10 МБ, config);
- проверка `UploadFile.size`, затем чтение `limit + 1` байт (память не растёт
  бесконечно);
- допустимые типы: JSON/YAML/plain, иначе **415**;
- превышение — **413** (`HTTP_413_CONTENT_TOO_LARGE`);
- затем UTF-8 и `parse_task_payload`.

Тесты (`tests/test_teacher.py`): 413 при маленьком лимите
(`monkeypatch settings.max_upload_bytes=100`), 415 для `text/csv`.

## Проверки

```
caddy validate ...                    # Valid configuration
pytest tests/test_teacher.py -q       # 8 passed
docker compose ... config --quiet     # OK
```

Значения зафиксированы в `RULES.md` §11.52 и `docs/PERFORMANCE.md` §4.
