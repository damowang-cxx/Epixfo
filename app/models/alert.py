from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlertLevel, AlertStatus, enum_values
from app.models.mixins import TimestampMixin


class WaybillAlert(Base, TimestampMixin):
    __tablename__ = "waybill_alerts"
    __table_args__ = (
        Index("idx_waybill_alerts_waybill_id", "waybill_id"),
        Index("idx_waybill_alerts_status", "status"),
        Index("idx_waybill_alerts_type", "alert_type"),
        Index("idx_waybill_alerts_level", "alert_level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    alert_level: Mapped[AlertLevel] = mapped_column(
        Enum(AlertLevel, name="alert_level", values_callable=enum_values),
        nullable=False,
        default=AlertLevel.WARNING,
        server_default=AlertLevel.WARNING.value,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status", values_callable=enum_values),
        nullable=False,
        default=AlertStatus.ACTIVE,
        server_default=AlertStatus.ACTIVE.value,
    )
    acknowledged_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    waybill = relationship("AirWaybill", backref="alerts")

    @property
    def waybill_no(self) -> str | None:
        return self.waybill.waybill_no if self.waybill else None
