from io import BytesIO
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.models import BoxDocument, CarrierAgent, ConsigneeContact, WarehouseReceipt
from app.schemas.box import BoxCreate
from app.services.warehouse_file_service import WarehouseFileService

_ = (CarrierAgent, ConsigneeContact)


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = None
        self.added = []
        self.deleted = None

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = obj

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 200 + len(self.added)
        self.added.append(obj)

    def delete(self, obj):
        self.deleted = obj

    def flush(self):
        return None


class FakeBoxRepository:
    def __init__(self) -> None:
        self.deleted_waybill_id = None
        self.document = None
        self.added_boxes = []
        self.added_items = []
        self.deleted_item_box_ids = []
        self.receipts_by_no = {}
        self.conflict_rows = []
        self.box = SimpleNamespace(
            id=4,
            current_waybill_id=7,
            warehouse_receipt_id=88,
            box_no="BOX-OLD",
            status="bound",
            is_general_cargo=False,
            unbound_reason=None,
            unbound_remark=None,
            raw_data={},
            items=[],
            document=None,
            warehouse_receipt=None,
            warehouse_waybill_no=None,
            goods_name=None,
            quantity=None,
            weight=None,
            original_volume_info=None,
            original_weight_volume_ratio=None,
            volume=None,
            weight_volume_ratio=None,
            source_row_number=None,
            document_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.boxes_list = [self.box]

    def add_document(self, document: BoxDocument) -> BoxDocument:
        document.id = 99
        self.document = document
        return document

    def delete_by_waybill(self, waybill_id: int) -> int:
        self.deleted_waybill_id = waybill_id
        return 3

    def add_boxes(self, boxes):
        self.added_boxes.extend(boxes)

    def get_by_waybill(self, waybill_id: int, box_id: int):
        for box in self.boxes_list:
            if box.current_waybill_id == waybill_id and box.id == box_id:
                return box
        return None

    def get_by_box_no(self, box_no: str):
        return next((box for box in self.boxes_list if box.box_no == box_no), None)

    def list_by_waybill(self, waybill_id: int):
        return [box for box in self.boxes_list if box.current_waybill_id == waybill_id]

    def list_conflicting_boxes(self, box_nos, target_warehouse_no):
        return self.conflict_rows

    def get_receipt_by_warehouse_no(self, warehouse_no: str):
        return self.receipts_by_no.get(warehouse_no)

    def add_receipt(self, receipt: WarehouseReceipt):
        receipt.id = 88
        self.receipts_by_no[receipt.warehouse_no] = receipt
        return receipt

    def list_by_receipt_id(self, receipt_id: int):
        return [box for box in self.boxes_list if box.warehouse_receipt_id == receipt_id]

    def get_receipt_by_id(self, receipt_id: int):
        for receipt in self.receipts_by_no.values():
            if receipt.id == receipt_id:
                return receipt
        return None

    def list_by_box_nos(self, box_nos):
        box_no_set = set(box_nos)
        return [box for box in self.boxes_list if box.box_no in box_no_set]

    def list_by_ids(self, box_ids):
        box_id_set = set(box_ids)
        return [box for box in self.boxes_list if box.id in box_id_set]

    def delete_items_for_box(self, box_id: int):
        self.deleted_item_box_ids.append(box_id)
        return 1

    def add_items(self, items):
        self.added_items.extend(items)


class FakeWaybillRepository:
    def __init__(self, waybill) -> None:
        self.waybill = waybill

    def get(self, waybill_id: int):
        return self.waybill if self.waybill.id == waybill_id else None


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息", "收货重量/方"])
    sheet.append(["BOX-001", "WH-AWB-001", "Shoes", 2, 10, "40*40*40", 0.156])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _invalid_xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息"])
    sheet.append(["", "WH-AWB-001", "Shoes", 2, 10, 4])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _fake_box(box_id: int, box_no: str, weight: str, volume: str):
    return SimpleNamespace(
        id=box_id,
        current_waybill_id=7,
        warehouse_receipt_id=88,
        box_no=box_no,
        status="bound",
        is_general_cargo=False,
        unbound_reason=None,
        unbound_remark=None,
        raw_data={},
        items=[],
        document=None,
        warehouse_receipt=None,
        warehouse_waybill_no=None,
        goods_name=None,
        quantity=None,
        weight=Decimal(weight),
        original_volume_info=None,
        original_weight_volume_ratio=None,
        volume=Decimal(volume),
        weight_volume_ratio=None,
        source_row_number=None,
        document_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_upload_for_waybill_replaces_boxes_and_updates_warehouse_no(tmp_path) -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service._store_file = lambda file_name, file_hash, content: tmp_path / file_name
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.upload_for_waybill(7, "AMS-IN-001.xlsx", _xlsx_bytes(), user)

    assert result.warehouse_no == "AMS-IN-001"
    assert result.success_count == 1
    assert result.document_id == 99
    assert waybill.warehouse_no == "AMS-IN-001"
    assert waybill.updated_by == 5
    added_box = next(item for item in service.db.added if item.__class__.__name__ == "Box")
    assert added_box.box_no == "BOX-001"
    assert added_box.current_waybill_id == 7
    assert added_box.warehouse_receipt_id == 88
    assert added_box.original_volume_info == "40*40*40"
    assert added_box.original_weight_volume_ratio == "0.156"
    assert str(added_box.volume) == "0.064"
    assert len(service.boxes.added_items) == 1
    assert service.db.committed is True


def test_update_box_no_updates_bound_box() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.update_box_no(7, 4, " BOX-NEW ", user)

    assert result.box_no == "BOX-NEW"
    assert service.db.committed is True
    assert service.db.refreshed is result


def test_update_box_toggles_general_cargo() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.update_box(7, 4, user, is_general_cargo=True)

    assert result.is_general_cargo is True
    assert service.db.committed is True


def test_create_box_requires_waybill_warehouse_no() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    with pytest.raises(HTTPException) as exc_info:
        service.create_box(7, BoxCreate(box_no="BOX-MANUAL"), user)

    assert exc_info.value.detail == "target_warehouse_no_required"


def test_create_box_binds_to_receipt_and_adds_manual_item() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.create_box(
        7,
        BoxCreate(
            box_no=" BOX-MANUAL ",
            warehouse_waybill_no="WH-AWB-001",
            goods_name="Shoes",
            quantity=2,
            weight=Decimal("10.5"),
            volume=Decimal("3"),
            is_general_cargo=True,
        ),
        user,
    )

    assert result.box_no == "BOX-MANUAL"
    assert result.current_waybill_id == 7
    assert result.warehouse_receipt_id == 88
    assert result.status == "bound"
    assert result.is_general_cargo is True
    assert str(result.weight_volume_ratio) == "3.500"
    assert len(service.boxes.added_items) == 1
    assert service.boxes.added_items[0].box_id == result.id
    assert service.boxes.added_items[0].warehouse_waybill_no == "WH-AWB-001"
    assert service.db.committed is True


def test_delete_box_removes_box_and_commits() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service.boxes.box.warehouse_receipt = WarehouseReceipt(
        warehouse_no="AMS-IN-001",
        waybill_id=7,
        total_quantity=1,
        total_weight=Decimal("10.000"),
        total_volume=Decimal("3.000"),
        weight_volume_ratio=Decimal("3.333"),
    )
    service.boxes.box.warehouse_receipt.id = 88
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    service.delete_box(7, 4, user)

    assert service.db.deleted is service.boxes.box
    assert service.db.committed is True


def test_recalculate_box_volumes_scales_to_booked_volume() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", booked_volume=Decimal("9.500"), warehouse_no="AMS-IN-001")
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service.boxes.boxes_list = [
        _fake_box(4, "BOX-001", "10.000", "6.000"),
        _fake_box(5, "BOX-002", "5.000", "4.000"),
    ]
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.recalculate_box_volumes(7, user)

    assert result.adjusted is True
    assert str(result.old_total_volume) == "10.000"
    assert str(result.new_total_volume) == "9.500"
    assert [str(box.volume) for box in service.boxes.boxes_list] == ["5.700", "3.800"]
    assert str(service.boxes.boxes_list[0].weight_volume_ratio) == "1.754"
    assert service.boxes.boxes_list[0].raw_data["volume_recalculation"]["booked_volume"] == "9.500"
    assert service.db.committed is True


def test_recalculate_box_volumes_rejects_excess_over_one_cubic_meter() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", booked_volume=Decimal("8.900"), warehouse_no="AMS-IN-001")
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service.boxes.boxes_list = [
        _fake_box(4, "BOX-001", "10.000", "6.000"),
        _fake_box(5, "BOX-002", "5.000", "4.000"),
    ]
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    with pytest.raises(HTTPException) as exc_info:
        service.recalculate_box_volumes(7, user)

    assert exc_info.value.detail["error_code"] == "warehouse_volume_exceeds_booking"
    assert "请移除部分箱" in exc_info.value.detail["message"]
    assert service.db.committed is False


def test_upload_reports_failed_rows_when_no_valid_rows(tmp_path) -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service._store_file = lambda file_name, file_hash, content: tmp_path / file_name
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    with pytest.raises(HTTPException) as exc_info:
        service.upload_for_waybill(7, "AMS-IN-001.xlsx", _invalid_xlsx_bytes(), user)

    assert "没有有效货物行" in exc_info.value.detail
    assert "第 2 行" in exc_info.value.detail


def test_upload_reports_box_conflicts_without_writing(tmp_path) -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    service._store_file = lambda file_name, file_hash, content: tmp_path / file_name
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])
    current_waybill = SimpleNamespace(id=8, waybill_no="999-00000001")
    current_receipt = SimpleNamespace(id=77, warehouse_no="OLD-IN")
    service.boxes.conflict_rows = [(SimpleNamespace(box_no="BOX-001"), current_waybill, current_receipt)]

    with pytest.raises(HTTPException) as exc_info:
        service.upload_for_waybill(7, "AMS-IN-001.xlsx", _xlsx_bytes(), user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_code"] == "warehouse_box_conflicts"
    assert exc_info.value.detail["conflicts"][0]["box_no"] == "BOX-001"
    assert service.db.added == []


def test_batch_bind_requires_target_waybill_warehouse_no() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no=None, updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    with pytest.raises(HTTPException) as exc_info:
        service.batch_bind_boxes([4], 7, user)

    assert exc_info.value.detail == "target_warehouse_no_required"


def test_batch_bind_moves_boxes_to_target_receipt() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.batch_bind_boxes([4], 7, user)

    assert result.updated_count == 1
    assert service.boxes.box.current_waybill_id == 7
    assert service.boxes.box.warehouse_receipt_id == 88
    assert service.boxes.box.status == "bound"
    assert service.boxes.box.unbound_reason is None
    assert service.boxes.box.unbound_remark is None
    assert service.db.committed is True


def test_batch_transfer_to_unbound_records_reason_and_remark() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.batch_transfer_boxes(
        [4],
        "unbound",
        user,
        unbound_reason="customs_inspection",
        unbound_remark=" 海关开箱查验 ",
    )

    assert result.updated_count == 1
    assert service.boxes.box.current_waybill_id is None
    assert service.boxes.box.warehouse_receipt_id is None
    assert service.boxes.box.status == "unbound"
    assert service.boxes.box.unbound_reason == "customs_inspection"
    assert service.boxes.box.unbound_remark == "海关开箱查验"
    assert service.db.committed is True


def test_batch_transfer_to_waybill_clears_unbound_reason() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-00000001", warehouse_no="AMS-IN-001", updated_by=None)
    service = WarehouseFileService.__new__(WarehouseFileService)
    service.db = FakeDb()
    service.boxes = FakeBoxRepository()
    service.boxes.box.current_waybill_id = None
    service.boxes.box.warehouse_receipt_id = None
    service.boxes.box.status = "unbound"
    service.boxes.box.unbound_reason = "other"
    service.boxes.box.unbound_remark = "待确认"
    service.waybills = FakeWaybillRepository(waybill)
    user = SimpleNamespace(id=5, is_superuser=True, roles=[])

    result = service.batch_transfer_boxes([4], "waybill", user, target_waybill_id=7)

    assert result.updated_count == 1
    assert service.boxes.box.current_waybill_id == 7
    assert service.boxes.box.warehouse_receipt_id == 88
    assert service.boxes.box.status == "bound"
    assert service.boxes.box.unbound_reason is None
    assert service.boxes.box.unbound_remark is None
    assert service.db.committed is True
