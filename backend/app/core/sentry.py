"""Sentry для backend (S35-002).

Политика PII: в Sentry **не уходят** тексты кода и промптов, email, IP и
токены. Это обеспечивается тремя слоями:

1. `send_default_pii=False` — SDK не прикладывает пользователя/куки сам;
2. `max_request_body_size="never"` — тело запроса не отправляется;
3. `before_send` — вычищает остатки: `request.data/cookies/query_string`,
   поля `user.email/ip_address/username`, секретные заголовки, `extra`-ключи
   с кодом/промптами/токенами, строки кода в stacktrace; email и IP в
   сообщениях маскируются.

Без `SENTRY_DSN` модуль работает как no-op: SDK не импортируется и не
инициализируется, ошибки не теряются, приложение не падает.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}\b")

#: Ключи, значение которых не отправляем никогда.
_SENSITIVE_KEYS = frozenset(
    {
        "code",
        "source",
        "prompt",
        "prompts",
        "messages",
        "completion",
        "content",
        "email",
        "username",
        "ip",
        "ip_address",
        "remote_addr",
        "password",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "cookies",
        "api_key",
        "dsn",
        "query",
        "query_string",
        "body",
        "data",
    }
)
#: Подстроки в имени ключа, которые тоже считаем чувствительными.
_SENSITIVE_FRAGMENTS = (
    "prompt",
    "code",
    "email",
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "cookie",
    "dsn",
    "forwarded",
)
#: Поля stacktrace, содержащие исходный код.
_CODE_FIELDS = frozenset({"context_line", "pre_context", "post_context"})


def _mask_text(value: str) -> str:
    """Маскировать email и IP в произвольной строке."""
    value = _EMAIL_RE.sub("<email>", value)
    value = _IPV4_RE.sub("<ip>", value)
    value = _IPV6_RE.sub("<ip>", value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _SENSITIVE_KEYS:
        return True
    return any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS)


def _scrub(value: Any, *, key: str | None = None) -> Any:
    """Рекурсивно вычистить PII/секреты из структуры события."""
    if key is not None:
        if key in _CODE_FIELDS:
            return "<filtered>"
        if _is_sensitive_key(key):
            return "<filtered>"

    if isinstance(value, dict):
        return {str(k): _scrub(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [_scrub(item, key=key) for item in value]
        return type(value)(items) if isinstance(value, tuple) else items
    if isinstance(value, str):
        return _mask_text(value)
    return value


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Очистить событие Sentry от PII перед отправкой (S35-002).

    Никогда не бросает исключений: ошибка фильтра не должна мешать обработке
    запроса или отправке самого события.
    """
    try:
        request = event.get("request")
        if isinstance(request, dict):
            for field in ("data", "cookies", "query_string"):
                request.pop(field, None)
            headers = request.get("headers")
            if isinstance(headers, dict):
                request["headers"] = {
                    key: _scrub(value, key=key) for key, value in headers.items()
                }

        user = event.get("user")
        if isinstance(user, dict):
            # Оставляем только внутренний идентификатор — без email/IP/логина.
            event["user"] = {
                key: value
                for key, value in user.items()
                if key in {"id", "segment"}
            }

        breadcrumbs = event.get("breadcrumbs")
        if isinstance(breadcrumbs, dict):
            values = breadcrumbs.get("values")
            if isinstance(values, list):
                breadcrumbs["values"] = [
                    _scrub(item) if isinstance(item, dict) else item
                    for item in values
                ]

        for field in ("extra", "contexts", "tags", "modules"):
            if field in event:
                event[field] = _scrub(event[field])

        if isinstance(event.get("message"), str):
            event["message"] = _mask_text(event["message"])
        logentry = event.get("logentry")
        if isinstance(logentry, dict):
            event["logentry"] = _scrub(logentry)

        if "exception" in event:
            event["exception"] = _scrub(event["exception"])

        return event
    except Exception as exc:  # noqa: BLE001 — фильтр не должен ломать отправку
        logger.warning("sentry_before_send_failed", error=str(exc))
        return event


def init_sentry() -> bool:
    """Инициализировать Sentry, если задан DSN.

    Returns:
        True — SDK инициализирован; False — DSN пуст или инициализация упала
        (приложение продолжает работать без Sentry).
    """
    if not settings.sentry_dsn:
        logger.info("sentry_disabled", reason="dsn_not_set")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            release=settings.sentry_release or settings.version,
            traces_sample_rate=max(0.0, min(settings.sentry_traces_sample_rate, 1.0)),
            send_default_pii=False,
            max_request_body_size="never",
            before_send=before_send,  # type: ignore[arg-type]
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        logger.info(
            "sentry_initialized",
            environment=settings.sentry_environment,
            release=settings.sentry_release or settings.version,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — Sentry не должен ронять старт
        logger.error("sentry_init_failed", error=str(exc))
        return False
