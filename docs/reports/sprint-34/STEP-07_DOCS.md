# S34-007 — документация

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено

## Обновлено

- `SECURITY.md` — поддерживаемые версии (0.6.x), правила эксплуатации:
  fail-fast `SECRET_KEY`, `DOCS_ENABLED`, `TRUSTED_PROXIES`, refresh только в
  теле, таблица лимитов.
- `docs/SPEC.md` §3 (таблица API) — refresh принимает JSON-тело.
- `docs/SPEC.md` §3.12 — `TRUSTED_PROXIES`, `DOCS_ENABLED`, стартовые проверки,
  таблица лимитов.
- `docs/RULES.md` §11.49 — клиентский IP, доверенные прокси, лимиты,
  refresh-токен в теле, неактивный пользователь.
- `docs/UPGRADE.md` §0.5 — breaking changes v0.6.0 (refresh body, 401 для
  деактивированных).
- `docs/CHANGELOG.md` — раздел `[0.6.0]`.
- `docs/KNOWN_ISSUES.md` — KI-032…KI-034 закрыты, KI-035 отложен на v0.7.0.
- `TODO_V0.4.md` — шапка и §0.0 с решениями владельца; релиз — v0.6.0.
- `TODO_V0.6.md` → `TODO_V0.7.md` — этап сдвинут на v0.7.0, добавлен KI-035.
- `README.md`, `docs/README.md`, `docs/RELEASES.md`, `docs/RULES.md`,
  `TODO_V0.5.md` — ссылки на переименованный план.
- `.env.example` — `TRUSTED_PROXIES`, `DOCS_ENABLED`.
- Версия: `backend/app/config.py`, `pyproject.toml`, `frontend/package.json` —
  `0.6.0`.

## i18n

Новых пользовательских строк нет: изменение refresh-транспорта не меняет UI,
серверные тексты 429 уже локализованы на русском и показываются через
`ApiError.detail`. Правки `ru.json`/`en.json` не требуются.

## Проверки

- `python -m ruff check app tests` — без замечаний.
- `python -m mypy app/...` по изменённым модулям — без ошибок.
- Ссылки на `TODO_V0.6.md` заменены; историческая запись в `CHANGELOG`
  помечена как переименованная.
