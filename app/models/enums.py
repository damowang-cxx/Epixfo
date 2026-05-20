from enum import StrEnum


class UserRoleCode(StrEnum):
    ADMIN = "admin"
    ROUTE_STAFF = "route_staff"
    CUSTOMER_SERVICE = "customer_service"
    CUSTOMS_STAFF = "customs_staff"


class WaybillLifecycleStatus(StrEnum):
    CREATED = "created"
    WAITING_MONITOR = "waiting_monitor"
    MONITORING = "monitoring"
    WAREHOUSE_RECEIVED = "warehouse_received"
    LOADED = "loaded"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    PICKUP_NOTIFIED = "pickup_notified"
    PICKED_UP = "picked_up"
    CLOSED = "closed"
    VOIDED = "voided"


class CarrierQueryMethod(StrEnum):
    PROTOCOL = "protocol"
    PLAYWRIGHT = "playwright"
    HYBRID = "hybrid"


class QueryStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class OfficialEventType(StrEnum):
    WAYBILL_RECEIVED = "waybill_received"
    CARGO_RECEIVED = "cargo_received"
    ORIGIN_CARGO_RECEIVED = "origin_cargo_received"
    CARGO_LOADED = "cargo_loaded"
    FLIGHT_DEPARTED = "flight_departed"
    FLIGHT_ARRIVED = "flight_arrived"
    TRANSIT_RECEIVED = "transit_received"
    DESTINATION_RECEIVED = "destination_received"
    PICKUP_NOTIFIED = "pickup_notified"
    PICKED_UP = "picked_up"
    CARGO_ASSEMBLED = "cargo_assembled"
    UNKNOWN = "unknown"


class NotificationChannel(StrEnum):
    SYSTEM = "system"
    WECHAT_RESERVED = "wechat_reserved"


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_cls]
