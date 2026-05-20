from app.models.enums import OfficialEventType


def normalize_status(status_text: str, event_city: str | None = None, origin_city: str | None = None) -> OfficialEventType:
    text = status_text or ""
    if "货物已被" in text and "提取" in text:
        return OfficialEventType.PICKED_UP
    if "已通知提货" in text or "已通知提取" in text:
        return OfficialEventType.PICKUP_NOTIFIED
    if "航班已到达" in text:
        return OfficialEventType.FLIGHT_ARRIVED
    if "航班已起飞" in text:
        return OfficialEventType.FLIGHT_DEPARTED
    if "货物已装机" in text:
        return OfficialEventType.CARGO_LOADED
    if "货物组装" in text:
        return OfficialEventType.CARGO_ASSEMBLED
    if "货物已接收" in text or "货物也接收" in text:
        if origin_city and event_city and origin_city in event_city:
            return OfficialEventType.ORIGIN_CARGO_RECEIVED
        return OfficialEventType.CARGO_RECEIVED
    if "运单已接收" in text:
        return OfficialEventType.WAYBILL_RECEIVED
    return OfficialEventType.UNKNOWN
