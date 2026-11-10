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

#: Значение `SECRET_KEY` из `.env.example`: не годится для production-запуска
DEFAULT_SECRET_KEY = "change_me_secret_key_for_jwt_encoding"


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
    version: str = "0.5.0"
    debug: bool = False
    #: Формат логов: `json` (production/CI) или `console` (dev) — S25-001
    log_level: str = "INFO"
    log_format: str = "json"
    #: Prometheus-метрики (S25-002): эндпоинт без авторизации для внутренней
    #: сети; в nginx наружу не публикуется
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
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
        """Sync URL для Alembic.

        Драйвер указан явно: SQLAlchemy 2.1 для схемы `postgresql://` по
        умолчанию выбирает psycopg 3, которого в проекте нет — в зависимостях
        psycopg2-binary.
        """
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
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
    secret_key: str = DEFAULT_SECRET_KEY
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
    #: Режим исполнения (S24): `native` — дочерний интерпретатор + Job Object/
    #: RLIMIT_AS; `container` — одноразовый контейнер с жёсткой изоляцией
    #: (сеть выключена, read-only rootfs, --cap-drop ALL). По умолчанию native;
    #: при недоступном Docker контейнерный режим откатывается на native с warning.
    executor_mode: str = "native"
    #: Образ контейнера-раннера (собирается из backend/sandbox_runner)
    executor_image: str = "ai-teacher-sandbox-runner:latest"
    executor_memory_limit: int = 128  # MB
    #: Максимум символов stdout в ответе (S13-005)
    executor_max_output: int = 100_000
    #: Сколько запусков песочницы выполняется одновременно (S13-003)
    executor_max_concurrency: int = 4
    #: Сколько секунд ждать свободный слот, прежде чем вернуть 503
    executor_queue_timeout: float = 5.0
    #: Пул «тёплых» интерпретаторов (S23-002): 0 — выключен (каждый батч
    #: поднимает свой процесс). Значение — сколько idle-процессов держать.
    #: Включать не больше `executor_max_concurrency`.
    executor_pool_size: int = 2
    #: Через сколько задач переиспользованный процесс перезапускается
    #: (страховка от накопления состояния импортированных модулей)
    executor_pool_max_tasks: int = 50

    #: Наполнять задачи при старте приложения (S14-002, KI-010)
    seed_on_start: bool = False

    # Retention (S26-003): сколько дней хранить; 0 — не удалять (по умолчанию
    # значения консервативные, применение — scripts/apply_retention.py)
    retention_chat_messages_days: int = 90
    retention_code_executions_days: int = 90
    retention_notifications_days: int = 180
    retention_audit_log_days: int = 365
    #: Сколько дней хранить историю попыток по задачам (S42-002)
    retention_task_attempts_days: int = 90
    #: Встроенный планировщик retention (KI-025): раз в сутки сам применяет
    #: `RETENTION_*_DAYS`, cron становится опциональным. По умолчанию выключен:
    #: включается в production (`docker-compose.prod.yml`) или через ENV.
    retention_scheduler_enabled: bool = False
    #: Время суточного запуска в UTC, формат ``HH:MM``
    retention_scheduler_at: str = "03:30"
    #: Размер батча удаления (как у CLI `--batch-size`)
    retention_scheduler_batch_size: int = 1000
    #: Email-уведомления (S28-004): выключены по умолчанию; в dev — лог
    notifications_email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@ai-teacher.local"
    #: Окно напоминания о дедлайне (S28-004)
    notifications_deadline_hours: int = 72
    #: Максимум строк в одном экспорте (S26-001); 0 — без лимита (не рекомендуется)
    export_max_rows: int = 100_000

    # Rate limiting (S11-003)
    #: В тестах отключается, чтобы лимиты не влияли на прогон
    rate_limit_enabled: bool = True

    # Redis-кэш справочных данных (S19-003)
    #: В тестах отключается, чтобы не ходить в реальный Redis
    cache_enabled: bool = True
    #: Время жизни записей кэша, секунд
    cache_ttl_seconds: int = 60

    # RAG-lite: семантический поиск по истории чата (S19-005)
    #: Семантический поиск включается только явно: без эмбеддингов работает ILIKE
    rag_enabled: bool = False
    #: Сколько сообщений возвращать по умолчанию
    rag_top_k: int = 5
    #: Минимальная близость (0..1) для семантической выдачи (S27-002);
    #: 0 — без порога. Ниже порога — fallback на ILIKE.
    rag_min_score: float = 0.0
    #: Размерность эмбеддингов; должна совпадать с колонкой chat_messages.embedding
    rag_embedding_dim: int = 1536
    #: Модель эмбеддингов на OpenAI-совместимом endpoint (LM Studio)
    rag_embedding_model: str = "local-embedding-model"
    #: Таймаут запроса эмбеддинга, секунд
    rag_embedding_timeout: float = 5.0


# Глобальный экземпляр настроек
settings = Settings()
