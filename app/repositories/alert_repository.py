from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import WaybillAlert
from app.models.enums import AlertStatus


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, alert_id: int) -> WaybillAlert | None:
        return self.db.get(WaybillAlert, alert_id)

    def list(
        self,
        status: AlertStatus | None = None,
        alert_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WaybillAlert]:
        query = select(WaybillAlert).options(selectinload(WaybillAlert.waybill)).order_by(WaybillAlert.id.desc())
        if status:
            query = query.where(WaybillAlert.status == status)
        if alert_type:
            query = query.where(WaybillAlert.alert_type == alert_type)
        return list(self.db.scalars(query.offset(skip).limit(limit)))

    def active_for_type(self, waybill_id: int, alert_type: str) -> WaybillAlert | None:
        return self.db.scalar(
            select(WaybillAlert).where(
                WaybillAlert.waybill_id == waybill_id,
                WaybillAlert.alert_type == alert_type,
                WaybillAlert.status == AlertStatus.ACTIVE,
            )
        )
