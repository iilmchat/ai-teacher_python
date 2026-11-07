"""Личные настройки уведомлений и языка (S45-004).

Настройки хранятся в `users.settings` (JSONB) под закрытым списком ключей.
Отсутствие ключа трактуется как значение по умолчанию, поэтому у
существующих пользователей ничего не меняется миграцией.
"""

from __future__ import annotations

from typing import Any

#: Допустимые языки интерфейса
LANGUAGES: tuple[str, ...] = ("ru", "en")

#: Ключи настроек уведомлений/языка со значениями по умолчанию.
#: `deadline_days` — за сколько дней до дедлайна напоминать.
DEFAULT_PREFERENCES: dict[str, Any] = {
    "language": "ru",
    "email_notifications": True,
    "deadline_notifications": True,
    "deadline_days": 3,
}


def notification_preferences(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Свести личные настройки с дефолтами (игнорируя посторонние ключи)"""
    merged = {**DEFAULT_PREFERENCES, **(settings or {})}
    prefs = {key: merged[key] for key in DEFAULT_PREFERENCES}
    if prefs["language"] not in LANGUAGES:
        prefs["language"] = DEFAULT_PREFERENCES["language"]
    prefs["deadline_days"] = max(1, min(14, int(prefs["deadline_days"])))
    return prefs
