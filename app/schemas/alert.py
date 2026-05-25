from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertLevel, AlertStatus


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    waybill_no: str | None = None
    alert_type: str
    alert_level: AlertLevel
    title: str
    description: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    status: AlertStatus
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
