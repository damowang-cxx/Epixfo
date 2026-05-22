"""Import all ORM models so SQLAlchemy metadata is fully registered."""

from app.models.alert import WaybillAlert
from app.models.audit import AuditLog
from app.models.auth import UserRefreshToken
from app.models.box import Box, BoxDocument, BoxItem, WarehouseReceipt
from app.models.carrier import Carrier, CarrierAgent, CarrierPrefixMapping, CarrierQueryConfig
from app.models.consignee import Consignee, ConsigneeContact, ConsigneeNotifyParty
from app.models.presence import UserDailyOnlineStats, UserLoginLog, UserPresenceLog
from app.models.system import AutoFlightQuerySettings
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
    "BoxItem",
    "Carrier",
    "CarrierAgent",
    "CarrierPrefixMapping",
    "CarrierQueryConfig",
    "Consignee",
    "ConsigneeContact",
    "ConsigneeNotifyParty",
    "AutoFlightQuerySettings",
    "Role",
    "User",
    "UserDailyOnlineStats",
    "UserLoginLog",
    "UserPresenceLog",
    "UserRefreshToken",
    "UserRole",
    "WarehouseReceipt",
    "WaybillAlert",
    "WaybillAssemblyEvent",
    "WaybillOfficialFlightSegment",
    "WaybillOfficialInfo",
    "WaybillPlan",
    "WaybillQuerySnapshot",
    "WaybillStatusEvent",
]
