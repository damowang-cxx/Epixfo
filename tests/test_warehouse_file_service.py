from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook

from app.models import BoxDocument
from app.services.warehouse_file_service import WarehouseFileService


class FakeDb:
    def __init__(self) -> None:
        self.committed = False

    def commit(self):
        self.committed = True


class FakeBoxRepository:
    def __init__(self) -> None:
        self.deleted_waybill_id = None
        self.document = None
        self.added_boxes = []

    def add_document(self, document: BoxDocument) -> BoxDocument:
        document.id = 99
        self.document = document
        return document

    def delete_by_waybill(self, waybill_id: int) -> int:
        self.deleted_waybill_id = waybill_id
        return 3

    def add_boxes(self, boxes):
        self.added_boxes.extend(boxes)


class FakeWaybillRepository:
    def __init__(self, waybill) -> None:
        self.waybill = waybill

    def get(self, waybill_id: int):
        return self.waybill if self.waybill.id == waybill_id else None


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息"])
    sheet.append(["BOX-001", "WH-AWB-001", "Shoes", 2, 10, 4])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_upload_for_waybill_replaces_boxes_and_updates_warehouse_no(tmp_path) -> None:
    waybill = SimpleNamespace(id=7, warehouse_no=None, updated_by=None)
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
    assert service.boxes.deleted_waybill_id == 7
    assert len(service.boxes.added_boxes) == 1
    assert service.boxes.added_boxes[0].box_no == "BOX-001"
    assert service.boxes.added_boxes[0].current_waybill_id == 7
    assert service.db.committed is True
