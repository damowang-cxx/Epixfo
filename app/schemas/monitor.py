from datetime import datetime

from pydantic import BaseModel, Field


class AutoFlightQuerySettingsUpdate(BaseModel):
    fallback_enabled: bool | None = None
    fallback_adapter_code: str | None = Field(default=None, max_length=64)
    query_interval_hours: int | None = Field(default=None, ge=1, le=24)
    scan_limit: int | None = Field(default=None, ge=1, le=500)


class AutoFlightQuerySettingsOut(BaseModel):
    fallback_enabled: bool
    fallback_adapter_code: str
    query_interval_hours: int
    scan_limit: int
    scheduler_process_enabled: bool
    scheduler_interval_seconds: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
