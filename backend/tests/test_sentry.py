"""Sentry backend: no-op без DSN и вычистка PII (S35-002)."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.core.sentry import before_send, init_sentry


def test_init_sentry_noop_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без DSN Sentry не инициализируется и приложение работает."""
    monkeypatch.setattr(settings, "sentry_dsn", "")

    assert init_sentry() is False


def test_before_send_removes_request_bodies() -> None:
    """Тело запроса, query string и cookies не уходят в Sentry."""
    event: dict[str, Any] = {
        "request": {
            "url": "https://example.test/api/v1/code/execute",
            "data": {"code": "print('secret solution')"},
            "cookies": {"session": "abc"},
            "query_string": "refresh_token=leaked",
            "headers": {
                "Authorization": "Bearer leaked-token",
                "Cookie": "session=abc",
                "Content-Type": "application/json",
                "X-Forwarded-For": "203.0.113.5",
                "User-Agent": "pytest",
            },
        }
    }

    result = before_send(event, {})

    request = result["request"]
    assert "data" not in request
    assert "cookies" not in request
    assert "query_string" not in request
    assert request["headers"]["Authorization"] == "<filtered>"
    assert request["headers"]["Cookie"] == "<filtered>"
    assert request["headers"]["X-Forwarded-For"] == "<filtered>"
    assert request["headers"]["Content-Type"] == "application/json"


def test_before_send_strips_user_pii() -> None:
    """Email, username и IP пользователя не отправляются."""
    event: dict[str, Any] = {
        "user": {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": "student@example.com",
            "username": "student",
            "ip_address": "203.0.113.5",
        }
    }

    result = before_send(event, {})

    assert result["user"] == {"id": "11111111-1111-1111-1111-111111111111"}


def test_before_send_filters_code_and_prompts_in_extra() -> None:
    """Код, промпты и токены в extra не отправляются."""
    event: dict[str, Any] = {
        "extra": {
            "user_code": "def solve():\n    return 42",
            "llm_prompt": "Объясни решение...",
            "refresh_token": "secret",
            "provider": "deepseek",
            "note": "contact student@example.com from 203.0.113.5",
        }
    }

    result = before_send(event, {})

    extra = result["extra"]
    assert extra["user_code"] == "<filtered>"
    assert extra["llm_prompt"] == "<filtered>"
    assert extra["refresh_token"] == "<filtered>"
    assert extra["provider"] == "deepseek"
    assert extra["note"] == "contact <email> from <ip>"


def test_before_send_removes_stacktrace_code() -> None:
    """Исходные строки кода из stacktrace не отправляются."""
    event: dict[str, Any] = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "boom for student@example.com",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "solution.py",
                                "context_line": "secret = 42",
                                "pre_context": ["# hidden"],
                                "post_context": ["# hidden"],
                            }
                        ]
                    },
                }
            ]
        }
    }

    result = before_send(event, {})

    frame = result["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["context_line"] == "<filtered>"
    assert frame["pre_context"] == "<filtered>"
    assert frame["post_context"] == "<filtered>"
    assert result["exception"]["values"][0]["value"] == "boom for <email>"


def test_before_send_never_raises() -> None:
    """Повреждённое событие не ломает обработку ошибки."""
    event: dict[str, Any] = {"request": "not-a-dict", "extra": object()}

    assert before_send(event, {}) is event
