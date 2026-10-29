"""
Доменные исключения приложения (RULES §3.1).

`HTTPException` используется только на уровне API; сервисы бросают эти
исключения, а обработчики в `app/main.py` переводят их в HTTP-коды.
"""


class AppError(Exception):
    """Базовая ошибка приложения"""

    status_code: int = 400
    detail: str = "Ошибка приложения"

    def __init__(self, detail: str | None = None) -> None:
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Запрошенный объект не найден"""

    status_code = 404
    detail = "Объект не найден"


class AccessDeniedError(AppError):
    """Нет доступа к объекту другого пользователя"""

    status_code = 403
    detail = "Нет доступа к этому объекту"


class ConflictError(AppError):
    """Конфликт состояния (например, дубликат)"""

    status_code = 409
    detail = "Конфликт состояния"


class ValidationError(AppError):
    """Некорректные входные данные"""

    status_code = 422
    detail = "Некорректные входные данные"


class ServiceUnavailableError(AppError):
    """Сервис временно перегружен (S13-003)"""

    status_code = 503
    detail = "Сервис временно недоступен, попробуйте позже"
