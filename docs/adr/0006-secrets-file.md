# ADR-006 — Секреты через `*_FILE` и Docker secrets

**Статус:** Accepted
**Дата:** 2026-11-12
**Контекст:** Секреты передавались только через ENV (`.env.prod`), что
неудобно для Docker secrets/K8s и повышает риск утечки через `docker inspect`.
Нужна стандартная поддержка файлов без поломки существующего деплоя.

## Решение

- `Settings` поддерживает `POSTGRES_PASSWORD_FILE`, `SECRET_KEY_FILE`,
  `DEEPSEEK_API_KEY_FILE`, `SENTRY_DSN_FILE`, `SMTP_PASSWORD_FILE`.
- Файл имеет приоритет над ENV; читается при инициализации, обрезаются только
  `\r\n`; пустой/нечитаемый файл → fail-fast.
- Prod-compose пробрасывает `*_FILE`; пример Docker secrets —
  `deploy/docker-compose.secrets.example.yml`.
- `deploy.sh` принимает либо ENV, либо `*_FILE`.
- Файлы `secrets/` в `.gitignore`, права 0600.

## Последствия

**Плюсы:**
- совместимо с Docker secrets/Swarm/K8s;
- секреты не видны в `docker inspect`/ENV-дампе;
- fail-fast вместо тихого пустого пароля.

**Минусы/риски:**
- путь файла — контейнерный (`/run/secrets/...`), хостовые проверки ограничены;
- нужны права/монтирование, иначе приложение не стартует (осознанно);
- ротация требует обновить файл и перезапустить сервис.

**Ссылки:** `app/config.py`, `deploy/docker-compose.secrets.example.yml`,
`scripts/deploy.sh`, `SECURITY.md`.
