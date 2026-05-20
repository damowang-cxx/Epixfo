"""Import all ORM models so SQLAlchemy metadata is fully registered."""

from app.models.alert import WaybillAlert
from app.models.audit import AuditLog
from app.models.auth import UserRefreshToken
from app.models.box import Box, BoxDocument
from app.models.carrier import Carrier, CarrierPrefixMapping, CarrierQueryConfig
from app.models.presence import UserDailyOnlineStats, UserLoginLog, UserPresenceLog
from app.models.user import Role, User, UserRole
from app.models.waybill import (
    AirWaybill,
    WaybillAssemblyEvent,
    WaybillOfficialFlightSegment,
    WaybillOfficialInfo,
    WaybillPlan,
    WaybillQuerySnapshot,
    WaybillStatusEvent,
)

__all__ = [
    "AirWaybill",
    "AuditLog",
    "Box",
    "BoxDocument",
    "Carrier",
    "CarrierPrefixMapping",
    "CarrierQueryConfig",
    "Role",
    "User",
    "UserDailyOnlineStats",
    "UserLoginLog",
    "UserPresenceLog",
    "UserRefreshToken",
    "UserRole",
    "WaybillAlert",
    "WaybillAssemblyEvent",
    "WaybillOfficialFlightSegment",
    "WaybillOfficialInfo",
    "WaybillPlan",
    "WaybillQuerySnapshot",
    "WaybillStatusEvent",
]
