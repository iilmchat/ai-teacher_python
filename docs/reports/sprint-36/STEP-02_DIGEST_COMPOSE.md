# S36-002 — digest-пиннинг и prod-compose

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## Compose

`docker-compose.prod.yml` больше не собирает приложение:

- `image: ${BACKEND_IMAGE:-ghcr.io/${GHCR_OWNER:-iilmchat}/ai-teacher-backend:${IMAGE_TAG:-v0.6.0}}`
  (аналогично frontend, sandbox);
- `BACKEND_IMAGE`/`FRONTEND_IMAGE`/`SANDBOX_IMAGE` — полные ссылки с digest,
  которые пишет `scripts/pin_images.sh`;
- `IMAGE_TAG` — тег релиза, если digest ещё не зафиксирован;
- `x-backend-image`/`x-frontend-image`/`x-sandbox-image` — YAML-якоря, чтобы
  не дублировать ссылки (backend + migrate, backend + executor).

## pin_images.sh

```bash
bash scripts/pin_images.sh --tag v0.6.0
```

- получает digest через `docker buildx imagetools inspect` (fallback: `docker
  pull` + `RepoDigests`);
- пишет в `.env.prod` `BACKEND_IMAGE=...@sha256:...`, `FRONTEND_IMAGE`,
  `SANDBOX_IMAGE`, `IMAGE_TAG`;
- `--dry-run`; `--digest name=sha256:...` для офлайн-теста/CI.

## Проверки

```
docker compose --env-file .env.prod.example -f docker-compose.prod.yml config --quiet
# OK

bash scripts/pin_images.sh --tag v0.6.0 --digest backend=sha256:aaa... ...
# OK: три ссылки записаны в .env.prod

bash scripts/deploy.sh --dry-run
# config валиден; образы — с @sha256
```

`backend/scripts/check_image_pins.py` обновлён: разрешает `${...}`/YAML-алиасы
для релизных образов, но запрещает `latest`; добавлен monitoring-compose.
Результат: `OK: все образы закреплены по digest (6 файлов)`.
