from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models import AirWaybill, WarehouseReceipt, WaybillPrebooking
from app.models.enums import UserRoleCode, WaybillLifecycleStatus
from app.schemas.warehouse_planner import (
    WarehousePlannerCommitRequest,
    WarehousePlannerRow,
    WarehousePlannerRowError,
    WarehousePlannerRowResult,
    WarehousePlannerRowsRequest,
    WarehousePlannerValidateResult,
)
from app.services.warehouse_planner_service import WarehousePlannerService


class FakeDb:
    def __init__(self, objects=None) -> None:
        self.objects = objects or {}
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, item_id: int):
        return self.objects.get((model, item_id))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _route_user():
    return SimpleNamespace(id=11, is_superuser=False, roles=[_role(UserRoleCode.ROUTE_STAFF)])


def _service(objects=None):
    service = WarehousePlannerService.__new__(WarehousePlannerService)
    service.db = FakeDb(objects)
    return service


def _prebooking(**overrides):
    data = {
        "id": 7,
        "status": "draft",
        "waybill_no": None,
        "carrier_agent_id": 3,
        "planned_flight_no": "QR8943",
        "planned_flight_date": date(2026, 6, 1),
        "outbound_date": None,
        "customs_staff_id": None,
        "booked_volume": Decimal("12.000"),
        "booked_weight": None,
        "density": None,
        "quotation": None,
        "include_tc": False,
        "departure_port": None,
        "destination_port": None,
        "planned_route_text": None,
        "converted_waybill_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_validate_prebooking_requires_formal_waybill_fields() -> None:
    service = _service({(WaybillPrebooking, 7): _prebooking()})
    row = WarehousePlannerRow(source_type="prebooking", source_id=7)

    result = service.validate_rows(WarehousePlannerRowsRequest(rows=[row]), _route_user())

    assert result.valid_count == 0
    assert result.invalid_count == 1
    messages = {error.message for error in result.results[0].errors}
    assert "waybill_no_required" in messages
    assert "departure_port_required" in messages
    assert "destination_port_required" in messages
    assert "planned_route_required" in messages
    assert "booked_weight_required" in messages
    assert "quotation_required" in messages


def test_validate_rejects_receipt_bound_to_other_waybill() -> None:
    waybill = SimpleNamespace(id=5, waybill_no="176-29600664", lifecycle_status=WaybillLifecycleStatus.CREATED)
    receipt = SimpleNamespace(id=9, warehouse_no="WH-9", waybill_id=22, prebooking_id=None)
    service = _service({(AirWaybill, 5): waybill, (WarehouseReceipt, 9): receipt})
    row = WarehousePlannerRow(
        source_type="waybill",
        source_id=5,
        waybill_no="176-29600664",
        receipt_ids=[9],
    )

    result = service.validate_rows(WarehousePlannerRowsRequest(rows=[row]), _route_user())

    assert result.invalid_count == 1
    assert result.results[0].errors[0].message == "receipt_bound_to_other_waybill:WH-9"


def test_commit_all_or_none_stops_before_writes_when_any_row_is_invalid() -> None:
    service = _service()
    first = WarehousePlannerRow(source_type="waybill", source_id=1, waybill_no="176-29600664")
    second = WarehousePlannerRow(source_type="prebooking", source_id=2)
    called = {"commit_row": False}

    service.validate_rows = lambda payload, user: WarehousePlannerValidateResult(
        valid_count=1,
        invalid_count=1,
        results=[
            WarehousePlannerRowResult(source_type="waybill", source_id=1, status="valid"),
            WarehousePlannerRowResult(
                source_type="prebooking",
                source_id=2,
                status="invalid",
                errors=[WarehousePlannerRowError(field="waybill_no", message="waybill_no_required")],
            ),
        ],
    )
    service._commit_row = lambda row, user: called.update(commit_row=True)

    result = WarehousePlannerService.commit(
        service,
        WarehousePlannerCommitRequest(mode="all_or_none", rows=[first, second]),
        _route_user(),
    )

    assert called["commit_row"] is False
    assert result.skipped_due_to_all_or_none is True
    assert result.success_count == 0
    assert result.failed_count == 1
    assert service.db.commits == 0


def test_commit_success_only_saves_successes_and_keeps_failed_rows() -> None:
    service = _service()
    first = WarehousePlannerRow(source_type="waybill", source_id=1, waybill_no="176-29600664")
    second = WarehousePlannerRow(source_type="prebooking", source_id=2)

    service.validate_rows = lambda payload, user: WarehousePlannerValidateResult(
        valid_count=1,
        invalid_count=1,
        results=[
            WarehousePlannerRowResult(source_type="waybill", source_id=1, status="valid"),
            WarehousePlannerRowResult(
                source_type="prebooking",
                source_id=2,
                status="invalid",
                errors=[WarehousePlannerRowError(field="waybill_no", message="waybill_no_required")],
            ),
        ],
    )
    service._commit_row = lambda row, user: WarehousePlannerRowResult(
        source_type=row.source_type,
        source_id=row.source_id,
        status="committed",
        waybill_id=99,
        waybill_no=row.waybill_no,
    )
    service._save_remaining_rows = lambda user, rows: setattr(service, "remaining_rows", rows)

    result = WarehousePlannerService.commit(
        service,
        WarehousePlannerCommitRequest(mode="success_only", rows=[first, second]),
        _route_user(),
    )

    assert result.success_count == 1
    assert result.failed_count == 1
    assert result.remaining_rows == [second]
    assert service.remaining_rows == [second]
    assert service.db.commits == 2
