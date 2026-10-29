"""
Конфигурация приложения с использованием pydantic-settings
"""
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# .env лежит в корне проекта (на два уровня выше backend/app)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Настройки приложения"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "AI Teacher for Python"
    version: str = "0.1.0"
    debug: bool = False
    # NoDecode: значение приходит строкой и режется нашим валидатором (CSV или JSON)
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> Any:
        """Поддержка формата CSV (a,b) и JSON-массива из ENV"""
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    # Database
    # KI-001: канонический 5432 занят чужим контейнером, проект использует 5434
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5434
    postgres_user: str = "ai_teacher"
    postgres_password: str = "change_me_password"
    postgres_db: str = "ai_teacher"

    @property
    def database_url(self) -> str:
        """URL для подключения к PostgreSQL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync URL для Alembic"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    # KI-001: канонический 6379 занят чужим контейнером, проект использует 6381
    redis_host: str = "127.0.0.1"
    redis_port: int = 6381
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """URL для подключения к Redis"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Security
    secret_key: str = "change_me_secret_key_for_jwt_encoding"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # LLM
    llm_provider: str = "deepseek"  # deepseek, lm_studio
    #: Резервный провайдер при недоступности основного (S12-002); пусто — выключен
    llm_fallback_provider: str = ""
    deepseek_api_key: str = "change_me_api_key"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    lm_studio_url: str = "http://localhost:1234/v1"
    #: Модель локального сервера (LM Studio отдаёт её в /v1/models)
    lm_studio_model: str = "local-model"
    llm_max_tokens: int = 2000
    llm_temperature: float = 0.7

    # Code Execution (S13)
    executor_timeout: int = 5  # секунд
    executor_memory_limit: int = 128  # MB
    #: Максимум символов stdout в ответе (S13-005)
    executor_max_output: int = 100_000
    #: Сколько запусков песочницы выполняется одновременно (S13-003)
    executor_max_concurrency: int = 4
    #: Сколько секунд ждать свободный слот, прежде чем вернуть 503
    executor_queue_timeout: float = 5.0

    # Rate limiting (S11-003)
    #: В тестах отключается, чтобы лимиты не влияли на прогон
    rate_limit_enabled: bool = True


# Глобальный экземпляр настроек
settings = Settings()
