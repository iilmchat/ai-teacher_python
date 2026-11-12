# S38-002 — секреты через `*_FILE`

**Дата:** 2026-11-12
**Спринт:** 38
**Статус:** завершено

## Конфигурация

`app/config.py`:

- новые поля `POSTGRES_PASSWORD_FILE`, `SECRET_KEY_FILE`,
  `DEEPSEEK_API_KEY_FILE`, `SENTRY_DSN_FILE`, `SMTP_PASSWORD_FILE`;
- `model_validator(mode="after")` читает файл, если путь задан:
  - приоритет файла выше ENV;
  - обрезаются только `\r\n` (внутренние пробелы сохраняются);
  - пустой/нечитаемый файл → `ValidationError` (fail-fast, не стартуем с
    пустым секретом).

## Compose и деплой

- `docker-compose.prod.yml`: `*_FILE` проброшены в postgres/backend/migrate;
  `POSTGRES_PASSWORD`/`SECRET_KEY` больше не обязательны на уровне compose
  (`:-`) — приложение валидирует при старте.
- `deploy/docker-compose.secrets.example.yml` — пример Docker secrets
  (`/run/secrets/...`) для postgres/backend/migrate.
- `scripts/deploy.sh`: принимает либо ENV, либо `*_FILE`; проверяет длину/
  дефолтность только для ENV-варианта.
- `.env.example`/`.env.prod.example` — примеры; `secrets/` в `.gitignore`.

## Проверки

```
pytest tests/test_secret_files.py -q      # 6 passed
docker compose ... config --quiet         # prod и secrets-override OK
```

Тесты: приоритет файла, postgres/deepseek/sentry, отсутствующий/пустой файл,
сохранение ENV без файла.
