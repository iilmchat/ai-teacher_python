"""Email-уведомления (S28-004).

По умолчанию выключены (`NOTIFICATIONS_EMAIL_ENABLED=false`): в dev-режиме
используется `LoggingEmailSender`, который просто пишет письмо в лог (MailHog
не обязателен). SMTP-ошибки **не должны ломать API** — вызывающий код получает
`False`, а в лог попадает warning.

Реальные отправки идут через `smtplib` в отдельном потоке (`asyncio.to_thread`),
чтобы не блокировать event loop.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


def mask_email(address: str) -> str:
    """Скрыть локальную часть адреса для логов (PII, PRIVACY.md)"""
    local, _, domain = address.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


class EmailSender(Protocol):
    """Минимальный интерфейс отправки письма (легко подменить в тестах)"""

    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class LoggingEmailSender:
    """Dev/CI: письма не уходят, а попадают в лог"""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info(
            "email_logged", to=mask_email(to), subject=subject, body_preview=body[:200]
        )


class SMTPEmailSender:
    """Отправка через SMTP (в потоке, с таймаутом)"""

    def __init__(self) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.sender = settings.smtp_from
        self.timeout = 10.0

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
            client.ehlo()
            if self.user:
                client.starttls()
                client.login(self.user, self.password)
            client.send_message(message)

    async def send(self, *, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        await asyncio.to_thread(self._send_sync, message)


def get_email_sender() -> EmailSender:
    """Выбрать отправителя: SMTP при включённом флаге и настроенном хосте"""
    if settings.notifications_email_enabled and settings.smtp_host:
        return SMTPEmailSender()
    return LoggingEmailSender()


async def send_assignment_email(
    sender: EmailSender,
    *,
    to: str,
    classroom_name: str,
    task_title: str,
    due_at: str | None,
) -> bool:
    """Письмо о новом назначении; False при любой ошибке (API не падает)"""
    if not to:
        return False
    subject = f"Новое задание: {task_title}"
    body = (
        f"Класс «{classroom_name}»: назначена задача «{task_title}».\n"
        + (f"Срок сдачи: {due_at}.\n" if due_at else "")
        + "\nОткройте AI Teacher for Python, чтобы приступить."
    )
    try:
        await sender.send(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать API
        logger.warning("email_send_failed", to=to, error=str(exc))
        return False
    return True


async def send_email_change_email(
    sender: EmailSender,
    *,
    to: str,
    new_email: str,
) -> bool:
    """Уведомление на старый адрес при смене e-mail (S45-002).

    Best-effort: `False` при любой ошибке, API запрос не ломает.
    """
    if not to:
        return False
    subject = "Адрес эл. почты изменён"
    body = (
        "Адрес эл. почты вашего аккаунта AI Teacher for Python изменён на "
        f"{new_email}.\nЕсли это не вы — немедленно смените пароль: "
        "другие устройства уйдут из сессии при следующем обновлении токенов."
    )
    try:
        await sender.send(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать API
        logger.warning("email_send_failed", to=to, error=str(exc))
        return False
    return True


__all__ = [
    "EmailSender",
    "LoggingEmailSender",
    "SMTPEmailSender",
    "get_email_sender",
    "send_assignment_email",
    "send_email_change_email",
]
