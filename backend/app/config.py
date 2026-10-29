"""
Конфигурация приложения с использованием pydantic-settings
"""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "AI Teacher for Python"
    version: str = "0.1.0"
    debug: bool = False
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
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
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
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
    deepseek_api_key: str = "change_me_api_key"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    lm_studio_url: str = "http://localhost:1234/v1"
    llm_max_tokens: int = 2000
    llm_temperature: float = 0.7

    # Code Execution
    executor_timeout: int = 5  # секунд
    executor_memory_limit: int = 128  # MB


# Глобальный экземпляр настроек
settings = Settings()
