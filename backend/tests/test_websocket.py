"""
Тесты WebSocket-протокола чата (S4-006).

Проверяем только авторизацию и базовый контракт: полноценный стриминг
требует БД и LLM, его поведение покрыто тестами `test_chat.py` на уровне
сервиса.
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_websocket_requires_token() -> None:
    """Без токена сервер присылает ошибку и закрывает соединение"""
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/chat/ws/{uuid4()}") as ws:
            message = ws.receive_json()

    assert message["type"] == "error"
    assert message["detail"] == "Требуется авторизация"


def test_websocket_rejects_invalid_token() -> None:
    """Некорректный токен не даёт доступа"""
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/chat/ws/{uuid4()}?token=garbage") as ws:
            message = ws.receive_json()

    assert message["type"] == "error"
