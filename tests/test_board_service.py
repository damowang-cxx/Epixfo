from types import SimpleNamespace

from app.models.enums import WaybillLifecycleStatus
from app.services.board_service import BoardService


def _waybill(
    waybill_no: str,
    *,
    consignee_contact_id: int | None = 1,
    lifecycle_status: WaybillLifecycleStatus = WaybillLifecycleStatus.CREATED,
    board_id: int | None = None,
):
    return SimpleNamespace(
        waybill_no=waybill_no,
        consignee_contact_id=consignee_contact_id,
        lifecycle_status=lifecycle_status,
        board_id=board_id,
    )


def test_generate_board_no_uses_expected_format() -> None:
    values = {BoardService._generate_board_no() for _ in range(30)}

    assert len(values) == 30
    for value in values:
        assert value.startswith("BUP_")
        assert len(value) == 8
        assert value[4:].isalnum()


def test_normalize_waybill_nos_deduplicates_and_reports_invalid() -> None:
    waybill_nos, errors = BoardService._normalize_waybill_nos(["78483707805", "784-83707805", "bad"])

    assert waybill_nos == ["784-83707805"]
    assert errors[0].waybill_no == "bad"
    assert errors[0].message == "invalid_waybill_no"


def test_collect_bind_errors_rejects_inactive_lifecycle() -> None:
    service = BoardService.__new__(BoardService)
    errors = service._collect_bind_errors(
        [_waybill("784-83707805", lifecycle_status=WaybillLifecycleStatus.PICKED_UP)],
        target_board=None,
    )

    assert errors[0].message == "lifecycle_not_allowed"


def test_collect_bind_errors_rejects_mismatched_consignee() -> None:
    service = BoardService.__new__(BoardService)
    errors = service._collect_bind_errors(
        [
            _waybill("784-83707805", consignee_contact_id=1),
            _waybill("784-83707806", consignee_contact_id=2),
        ],
        target_board=None,
    )

    assert errors[0].waybill_no == "784-83707806"
    assert errors[0].message == "consignee_mismatch"


def test_collect_bind_errors_rejects_existing_board_binding() -> None:
    service = BoardService.__new__(BoardService)
    errors = service._collect_bind_errors([_waybill("784-83707805", board_id=9)], target_board=None)

    assert errors[0].message == "waybill_already_bound"


def test_collect_bind_errors_keeps_existing_empty_consignee_rule() -> None:
    service = BoardService.__new__(BoardService)
    board = SimpleNamespace(id=1, consignee_contact_id=None, waybills=[_waybill("784-83707804", consignee_contact_id=None)])

    errors = service._collect_bind_errors([_waybill("784-83707805", consignee_contact_id=5)], target_board=board)

    assert errors[0].message == "consignee_mismatch"
