from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.carrier_query.registry import GENERAL_ADAPTER_CODE, registry
from app.core.config import settings
from app.core.exceptions import bad_request
from app.models.system import AutoFlightQuerySettings
from app.schemas.monitor import AutoFlightQuerySettingsOut, AutoFlightQuerySettingsUpdate


DEFAULT_SETTINGS_ID = 1


class AutoFlightQuerySettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_model(self, commit_on_create: bool = False) -> AutoFlightQuerySettings:
        item = self.db.get(AutoFlightQuerySettings, DEFAULT_SETTINGS_ID)
        if item is None:
            item = AutoFlightQuerySettings(
                id=DEFAULT_SETTINGS_ID,
                fallback_enabled=True,
                fallback_adapter_code=GENERAL_ADAPTER_CODE,
                query_interval_hours=2,
                scan_limit=50,
            )
            self.db.add(item)
            self.db.flush()
            if commit_on_create:
                self.db.commit()
                self.db.refresh(item)
        return item

    def get(self) -> AutoFlightQuerySettingsOut:
        return self._to_out(self.get_model(commit_on_create=True))

    def update(self, payload: AutoFlightQuerySettingsUpdate) -> AutoFlightQuerySettingsOut:
        item = self.get_model()
        data = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
        adapter_code = data.get("fallback_adapter_code")
        if adapter_code is not None and registry.get(adapter_code) is None:
            raise bad_request("fallback_adapter_not_found")
        for key, value in data.items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return self._to_out(item)

    def _to_out(self, item: AutoFlightQuerySettings) -> AutoFlightQuerySettingsOut:
        return AutoFlightQuerySettingsOut(
            fallback_enabled=item.fallback_enabled,
            fallback_adapter_code=item.fallback_adapter_code,
            query_interval_hours=item.query_interval_hours,
            scan_limit=item.scan_limit,
            scheduler_process_enabled=settings.enable_monitor_scheduler,
            scheduler_interval_seconds=settings.monitor_scheduler_interval_seconds,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
