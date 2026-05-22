from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class AutoFlightQuerySettings(Base, TimestampMixin):
    __tablename__ = "auto_flight_query_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, default=1)
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    fallback_adapter_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="general_adapter",
        server_default="general_adapter",
    )
    query_interval_hours: Mapped[int] = mapped_column(nullable=False, default=2, server_default="2")
    scan_limit: Mapped[int] = mapped_column(nullable=False, default=50, server_default="50")
