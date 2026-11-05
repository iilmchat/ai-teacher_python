"""
Выгрузка диалога чата (S43-004).

Два формата: Markdown-транскрипт (для чтения и вставки в документ) и JSON
(совместим с `ChatSessionWithMessages` — его можно сохранить как есть).
"""

from urllib.parse import quote

from app.models.chat import ChatMessage, ChatSession, MessageRole

#: Заголовок Markdown-транскрипта
TRANSCRIPT_TITLE = "# Диалог с ассистентом"

#: Подпись роли в транскрипте
ROLE_LABELS = {
    MessageRole.USER: "Ученик",
    MessageRole.ASSISTANT: "Ассистент",
    MessageRole.SYSTEM: "Система",
}


def _format_time(value: object) -> str:
    """Время сообщения в формате ЧЧ:ММ (без таймзоны — локальное время БД)"""
    formatted = getattr(value, "strftime", None)
    if formatted is None:
        return ""
    return str(formatted("%H:%M"))


def render_transcript_markdown(
    session: ChatSession, messages: list[ChatMessage]
) -> str:
    """Markdown-транскрипт диалога (S43-004).

    Текст сообщений вставляется как есть: блоки кода и разметка сохраняются,
    спецсимволы не экранируются — иначе транскрипт нельзя было бы читать.
    """
    lines: list[str] = [
        TRANSCRIPT_TITLE,
        "",
        f"- Сессия: `{session.id}`",
        f"- Уровень: {session.level}",
        f"- Заголовок: {session.title or '—'}",
        f"- Создана: {_format_time(session.created_at)}",
        f"- Сообщений: {len(messages)}",
        "",
    ]
    for message in messages:
        label = ROLE_LABELS.get(message.role, message.role.value)
        lines.append(f"## {label} · {_format_time(message.created_at)}")
        lines.append("")
        body = message.content.strip()
        lines.append(body if body else "_(пусто)_")
        lines.append("")
    return "\n".join(lines)


def transcript_filename(session: ChatSession, extension: str) -> str:
    """Имя файла выгрузки: заголовок сессии или идентификатор"""
    title = (session.title or "").strip()
    if title:
        safe = "".join(
            char if char.isalnum() or char in " -_" else "_" for char in title
        ).strip()
        safe = "-".join(safe.split())[:60]
    else:
        safe = str(session.id)
    return f"chat-{safe or session.id}.{extension}"


def content_disposition(filename: str) -> str:
    """Заголовок вложения с ASCII-именем и UTF-8-версией (RFC 6266).

    Заголовки HTTP ограничены latin-1, поэтому кириллическое имя файла
    передаётся в параметре `filename*`, а `filename` содержит безопасный
    ASCII-вариант.
    """
    ascii_name = filename.encode("ascii", "ignore").decode().strip() or "chat.md"
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
