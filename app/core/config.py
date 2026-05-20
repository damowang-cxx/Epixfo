from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/epixfo"
    jwt_secret: str = "change-me-in-production"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    app_timezone: str = "Asia/Shanghai"
    enable_monitor_scheduler: bool = False
    monitor_scheduler_interval_seconds: int = 60
    weight_mismatch_absolute_threshold: float = 1.0
    weight_mismatch_percent_threshold: float = 0.02
    volume_mismatch_absolute_threshold: float = 0.01
    volume_mismatch_percent_threshold: float = 0.02
    csair_captcha_debug: bool = False
    csair_captcha_debug_dir: str = "./runtime/csair-captcha"
    csair_captcha_offset_range: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
