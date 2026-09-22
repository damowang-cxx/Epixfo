from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql

from app.api.v1.carriers import delete_destination_port
from app.models.destination_port import DestinationPort
from app.schemas.destination_port import DestinationPortCreate, ReceiptDestinationUpdate
from app.schemas.waybill import WaybillCreate
from app.services.destination_port_service import DestinationPortService, receipt_destination_ports
from app.services.warehouse_file_service import WarehouseFileService
from app.services.waybill_service import WaybillService


class FakeDb:
    def __init__(self):
        self.ports = {code: DestinationPort(code=code) for code in ("AMS", "LHR", "JFK")}
        self.commits = 0
        self.rollbacks = 0
        self.added = []
        self.deleted = []
        self.scalar_results = []
        self.statements = []

    def get(self, model, key):
        return self.ports.get(key) if model is DestinationPort else None

    def add(self, item):
        self.added.append(item)

    def delete(self, item):
        self.deleted.append(item)
        self.ports.pop(item.code)

    def scalar(self, statement):
        self.statements.append(statement)
        return self.scalar_results.pop(0) if self.scalar_results else None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def user(role="route_staff"):
    return SimpleNamespace(id=1, is_superuser=False, roles=[SimpleNamespace(code=role)])


def receipt_service(**values):
    receipt = SimpleNamespace(id=9, warehouse_no="WH-9", waybill_id=None, prebooking_id=None,
                              channel_tags=["AMS"], destination_ports_override=None)
    receipt.__dict__.update(values)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = SimpleNamespace(get_receipt_by_id=lambda _: receipt, list_by_receipt_id=lambda _: [])
    service.get_receipt_summary = lambda _: receipt
    return service, receipt


def test_destination_code_normalization_and_registry_validation():
    payload = DestinationPortCreate(code=" jfk ")
    assert payload.code == "JFK"
    service = DestinationPortService(FakeDb())
    assert service.require(" jfk ") == "JFK"
    for value in (None, "", " ", "ZZZ"):
        with pytest.raises(HTTPException):
            service.require(value)
    for value in ("A", "ABC DEF", "A" * 17):
        with pytest.raises(ValidationError):
            DestinationPortCreate(code=value)


def test_destination_creation_and_duplicate_rollback():
    db = FakeDb()
    assert DestinationPortService(db).create("CDG").code == "CDG"
    assert db.commits == 1
    def duplicate():
        raise IntegrityError("insert", {}, Exception("duplicate"))
    db.commit = duplicate
    with pytest.raises(HTTPException):
        DestinationPortService(db).create("AMS")
    assert db.rollbacks == 1


def test_unused_destination_can_be_deleted():
    db = FakeDb()

    DestinationPortService(db).delete(" jfk ")

    assert [item.code for item in db.deleted] == ["JFK"]
    assert "JFK" not in db.ports
    assert db.commits == 1


def test_receipt_uses_manual_destination_instead_of_raw_channel_tags():
    db = FakeDb()

    DestinationPortService(db).delete("JFK")

    automatic_receipt_query = str(db.statements[-1].compile(dialect=postgresql.dialect()))
    assert "destination_ports_override IS NULL" in automatic_receipt_query
    assert "channel_tags @>" in automatic_receipt_query


@pytest.mark.parametrize("scalar_results", [[1], [None, 1], [None, None, 1], [None, None, None, 1]])
def test_destination_in_use_cannot_be_deleted(scalar_results):
    db = FakeDb()
    db.scalar_results = scalar_results

    with pytest.raises(HTTPException) as error:
        DestinationPortService(db).delete("AMS")

    assert error.value.status_code == 400
    assert "AMS" in error.value.detail
    assert db.deleted == []
    assert db.commits == 0


def test_delete_missing_destination_returns_not_found():
    db = FakeDb()

    with pytest.raises(HTTPException) as error:
        DestinationPortService(db).delete("CDG")

    assert error.value.status_code == 404
    assert db.deleted == []


@pytest.mark.parametrize("role", ["customer_service", "customs_staff"])
def test_delete_destination_requires_management_role(role):
    db = FakeDb()

    with pytest.raises(HTTPException) as error:
        delete_destination_port("AMS", current_user=user(role), db=db)

    assert error.value.status_code == 403
    assert db.deleted == []


@pytest.mark.parametrize("ports,effective", [([" jfk "], ["JFK"]), ([], []), (None, ["AMS"])])
def test_manual_destination_set_clear_and_restore_auto(ports, effective):
    service, receipt = receipt_service(destination_ports_override=["LHR"])
    result = service.update_receipt_destination(9, ports, user())
    assert result is receipt
    assert receipt_destination_ports(receipt) == effective
    assert receipt.channel_tags == ["AMS"]
    assert service.db.commits == 1


def test_manual_destination_survives_receipt_refresh():
    service, receipt = receipt_service(destination_ports_override=["JFK"])
    service._refresh_receipt_totals(receipt)
    assert receipt.channel_tags == []
    assert receipt_destination_ports(receipt) == ["JFK"]


@pytest.mark.parametrize("field", ["waybill_id", "prebooking_id"])
def test_bound_receipt_cannot_change_destination(field):
    service, receipt = receipt_service(**{field: 3})
    with pytest.raises(HTTPException):
        service.update_receipt_destination(9, ["JFK"], user())
    assert receipt.destination_ports_override is None
    assert service.db.commits == 0


@pytest.mark.parametrize("role", ["customer_service", "customs_staff"])
def test_read_only_roles_cannot_change_destination(role):
    service, receipt = receipt_service()
    with pytest.raises(HTTPException) as error:
        service.update_receipt_destination(9, ["JFK"], user(role))
    assert error.value.status_code == 403
    assert receipt.destination_ports_override is None
    assert service.db.commits == 0


def test_unknown_destination_rejected_without_changes():
    service, receipt = receipt_service(destination_ports_override=["LHR"])
    with pytest.raises(HTTPException):
        service.update_receipt_destination(9, ["ZZZ"], user())
    assert receipt.destination_ports_override == ["LHR"]
    assert service.db.commits == 0
    with pytest.raises(ValidationError):
        ReceiptDestinationUpdate(destination_ports=["AMS", "LHR"])


@pytest.mark.parametrize("port", [None, "", "ZZZ"])
def test_create_waybill_rejects_missing_or_unknown_destination_before_writing(port):
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb()
    with pytest.raises(HTTPException):
        service.create(WaybillCreate(waybill_no="784-83707805", destination_port=port), user())
    assert service.db.commits == 0
    assert service.db.added == []
