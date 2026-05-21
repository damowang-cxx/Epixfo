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
    emirates_skycargo_base_url: str = "https://eskycargo.emirates.com"
    emirates_skycargo_cache_dir: str = "./runtime/emirates-skycargo"
    emirates_skycargo_cache_ttl_seconds: int = 1800
    emirates_skycargo_timeout_seconds: int = 60
    fiftyone_tracking_base_url: str = "https://www.51tracking.com"
    fiftyone_tracking_cache_dir: str = "./runtime/51tracking-aircargo"
    fiftyone_tracking_cache_ttl_seconds: int = 1800
    fiftyone_tracking_timeout_seconds: int = 60
    fiftyone_tracking_lang: str = "cn"
    fiftyone_tracking_allow_stale_on_error: bool = True

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
