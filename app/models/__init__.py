"""SQLAlchemy ORM models package."""

_MODEL_EXPORTS = {
    "AuditLog": ("app.models.audit", "AuditLog"),
    "Box": ("app.models.box", "Box"),
    "BoxDocument": ("app.models.box", "BoxDocument"),
    "BoxItem": ("app.models.box", "BoxItem"),
    "WarehouseReceipt": ("app.models.box", "WarehouseReceipt"),
    "Carrier": ("app.models.carrier", "Carrier"),
    "CarrierAgent": ("app.models.carrier", "CarrierAgent"),
    "CarrierPrefixMapping": ("app.models.carrier", "CarrierPrefixMapping"),
    "CarrierQueryConfig": ("app.models.carrier", "CarrierQueryConfig"),
    "Consignee": ("app.models.consignee", "Consignee"),
    "ConsigneeContact": ("app.models.consignee", "ConsigneeContact"),
    "ConsigneeNotifyParty": ("app.models.consignee", "ConsigneeNotifyParty"),
    "AutoFlightQuerySettings": ("app.models.system", "AutoFlightQuerySettings"),
    "Role": ("app.models.user", "Role"),
    "User": ("app.models.user", "User"),
    "UserRole": ("app.models.user", "UserRole"),
    "UserRefreshToken": ("app.models.auth", "UserRefreshToken"),
    "UserDailyOnlineStats": ("app.models.presence", "UserDailyOnlineStats"),
    "UserLoginLog": ("app.models.presence", "UserLoginLog"),
    "UserPresenceLog": ("app.models.presence", "UserPresenceLog"),
    "AirWaybill": ("app.models.waybill", "AirWaybill"),
    "WaybillBoard": ("app.models.waybill", "WaybillBoard"),
    "WaybillAlert": ("app.models.alert", "WaybillAlert"),
    "WaybillAssemblyEvent": ("app.models.waybill", "WaybillAssemblyEvent"),
    "WaybillOfficialFlightSegment": ("app.models.waybill", "WaybillOfficialFlightSegment"),
    "WaybillOfficialInfo": ("app.models.waybill", "WaybillOfficialInfo"),
    "WaybillCustomsAccessGrant": ("app.models.waybill", "WaybillCustomsAccessGrant"),
    "WaybillPlan": ("app.models.waybill", "WaybillPlan"),
    "WaybillQuerySnapshot": ("app.models.waybill", "WaybillQuerySnapshot"),
    "WaybillStatusEvent": ("app.models.waybill", "WaybillStatusEvent"),
    "WaybillViewLog": ("app.models.waybill", "WaybillViewLog"),
}


def __getattr__(name: str):
    if name not in _MODEL_EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _MODEL_EXPORTS[name]
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = sorted(_MODEL_EXPORTS)
