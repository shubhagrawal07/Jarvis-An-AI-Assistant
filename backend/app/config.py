from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    openai_api_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    firebase_credentials_path: str = ""

    # Default local times (user can override per user in DB)
    morning_summary_hour: int = 8
    morning_summary_minute: int = 0
    eod_prompt_start_hour: int = 21
    eod_prompt_end_hour: int = 23
    auto_close_grace_minutes_after_midnight: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
