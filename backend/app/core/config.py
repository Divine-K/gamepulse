from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root holds the shared .env used by docker-compose and the backend.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # the shared .env also holds POSTGRES_* and VITE_* keys
    )

    app_name: str = "GamePulse"
    app_env: str = "development"
    log_level: str = "INFO"

    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 60
    auth_rate_limit_per_minute: int = 10
    game_api_rate_limit_per_minute: int = 600  # per game (API key owner)

    # A session with no heartbeat for this long is marked abandoned.
    session_timeout_minutes: int = 15
    session_reaper_interval_seconds: int = 60

    # WebSockets
    ws_auth_timeout_seconds: float = 5.0
    ws_max_connections_per_game: int = 20
    ws_queue_size: int = 256  # per-connection buffer; a client that falls behind is dropped
    leaderboard_cache_ttl_seconds: int = 30

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = ["http://localhost:5173"]
    max_request_body_bytes: int = 1_000_000  # larger bodies get 413 before they are read

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must start with postgresql+psycopg://")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
