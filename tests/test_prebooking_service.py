from datetime import date
from types import SimpleNamespace

from app.schemas.waybill import WaybillCreate
from app.services.prebooking_service import PrebookingService


def _prebooking(**overrides):
    values = {
        "carrier_agent_id": 1,
        "booked_volume": 12,
        "planned_flight_date": date(2026, 6, 1),
        "outbound_date": date(2026, 5, 30),
        "waybill_no": None,
        "departure_port": None,
        "destination_port": None,
        "planned_flight_no": None,
        "planned_route_text": None,
        "consignee": None,
        "consignee_contact_id": None,
        "customs_staff_id": None,
        "data_charge": None,
        "delivery_time": None,
        "document_cutoff_time": None,
        "booked_weight": None,
        "density": None,
        "quotation": None,
        "include_tc": False,
        "warehouse_data_remark": None,
        "notify_pickup": False,
        "pickup_time": None,
        "internal_remark": None,
        "customer_remark": None,
        "air_freight_cost": None,
        "other_charge": None,
        "payment_date": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_convert_payload_inherits_prebooking_outbound_date() -> None:
    service = PrebookingService.__new__(PrebookingService)
    merged = service._merge_convert_payload(
        _prebooking(),
        WaybillCreate(waybill_no="176-29600664"),
    )

    assert merged["outbound_date"] == date(2026, 5, 30)
    assert merged["departure_port"] == "CAN"


def test_convert_payload_can_override_outbound_date() -> None:
    service = PrebookingService.__new__(PrebookingService)
    merged = service._merge_convert_payload(
        _prebooking(),
        WaybillCreate(waybill_no="176-29600664", outbound_date=date(2026, 6, 3)),
    )

    assert merged["outbound_date"] == date(2026, 6, 3)


def test_convert_payload_can_explicitly_clear_internal_remark() -> None:
    service = PrebookingService.__new__(PrebookingService)
    merged = service._merge_convert_payload(
        _prebooking(internal_remark="original note"),
        WaybillCreate(waybill_no="176-29600664", internal_remark=None),
    )

    assert merged["internal_remark"] is None
