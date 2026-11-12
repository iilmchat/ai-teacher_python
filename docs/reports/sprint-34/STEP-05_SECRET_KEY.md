# S34-005 — fail-fast при небезопасном SECRET_KEY

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено

## Проблема

Раньше при дефолтном или коротком `SECRET_KEY` приложение писало `error`-лог,
но продолжало работать. В production это позволяло подделать JWT любому, кто
видел `.env.example`.

## Изменения

- `backend/app/config.py`:
  - `SECRET_KEY_MIN_LENGTH = 32`;
  - `InsecureSettingsError(RuntimeError)`;
  - `validate_security_settings()` — при `DEBUG=false` бросает исключение,
    если ключ дефолтный или короче 32 символов; при `DEBUG=true` — no-op.
- `backend/app/main.py` — вызов `validate_security_settings()` в начале
  `lifespan`: сервер не стартует с небезопасной конфигурацией.
- `backend/tests/test_security_settings.py` — 4 теста: дефолтный ключ,
  короткий ключ, валидный ключ, `DEBUG=true`.

## Проверки

```
cd backend && python -m pytest tests/test_security_settings.py -q   # 8 passed
```

## Эксплуатация

В `.env.example` остаётся `DEBUG=true` для локальной разработки. Production
обязан задать `DEBUG=false` и случайный `SECRET_KEY` ≥ 32 символов; иначе
`uvicorn` завершится с `InsecureSettingsError`. Отражено в `SECURITY.md` и
`SPEC.md` §3.12.
