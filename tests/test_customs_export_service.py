from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.services.customs_export_service import CustomsExportService


class FakeBoxRepository:
    def __init__(self, boxes):
        self._boxes = boxes

    def list_by_waybill(self, waybill_id: int):
        return self._boxes


def _make_service(boxes):
    service = CustomsExportService.__new__(CustomsExportService)
    service.boxes = FakeBoxRepository(boxes)
    return service


def _make_waybill(**overrides):
    defaults = {
        "id": 7,
        "waybill_no": "176-29600664",
        "warehouse_data_remark": "入国航1号货站，喜提达打板截单时间：21号 20:00",
        "consignee": None,
        "consignee_contact": SimpleNamespace(
            name="ALLINE BV",
            address="Capronilaan 37 Schiphol-Rijk the Netherlands 1119 NG",
            email="import@alline.global",
            phone="+31 629 809 005",
            tax_info="VAT number: NL863476971B01",
            notify_party=None,
        ),
        "plan": SimpleNamespace(
            planned_flight_no="EK9871",
            planned_flight_date=date(2026, 5, 22),
            planned_route_text="CAN- DWC - AMS",
        ),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _load_export(workbook_bytes: bytes):
    return load_workbook(BytesIO(workbook_bytes))


def test_customs_export_includes_two_sheets_and_single_box_row() -> None:
    box = SimpleNamespace(
        box_no="DHLAE57542",
        warehouse_waybill_no="CP147969890DE",
        goods_name="SPORTS SHOES",
        quantity=10,
        weight=Decimal("13.500"),
        volume=Decimal("0.080"),
        weight_volume_ratio=Decimal("168.750"),
        items=[],
    )
    workbook = _load_export(_make_service([box]).build_waybill_export(_make_waybill()))

    assert workbook.sheetnames == ["入仓数据", "提单资料"]
    inbound = workbook["入仓数据"]
    assert [cell.value for cell in inbound[1]] == ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息", "收货重量/方"]
    assert [cell.value for cell in inbound[2]] == [
        "DHLAE57542",
        "CP147969890DE",
        "SPORTS SHOES",
        10,
        "13.5",
        "0.080",
        "168.750",
    ]

    waybill_sheet = workbook["提单资料"]
    rows = {row[0].value: row[1].value for row in waybill_sheet.iter_rows(min_row=1, max_col=2)}
    assert rows["提单号"] == "176-29600664"
    assert rows["发货人"] is None
    assert rows["品名"] is None
    assert "ALLINE BV" in rows["收货人"]
    assert "EK9871/22MAY" in rows["航班号截单时间隐含签名仓库/打板交单地址"]
    assert "航程：CAN- DWC - AMS" in rows["航班号截单时间隐含签名仓库/打板交单地址"]
    assert "喜提达打板截单时间" in rows["航班号截单时间隐含签名仓库/打板交单地址"]


def test_customs_export_expands_multi_item_box_with_blank_repeated_box_fields() -> None:
    box = SimpleNamespace(
        box_no="DHLAE57698",
        warehouse_waybill_no="CP147989086DE",
        goods_name="衣服",
        quantity=3,
        weight=Decimal("1.770"),
        volume=Decimal("0.150"),
        weight_volume_ratio=Decimal("11.800"),
        items=[
            SimpleNamespace(warehouse_waybill_no="CP147989086DE", goods_name="衣服", quantity=1, weight=Decimal("0.590")),
            SimpleNamespace(warehouse_waybill_no="CP147905449DE", goods_name="鞋", quantity=1, weight=Decimal("0.590")),
        ],
    )
    workbook = _load_export(_make_service([box]).build_waybill_export(_make_waybill()))
    inbound = workbook["入仓数据"]

    assert [cell.value for cell in inbound[2]] == ["DHLAE57698", "CP147989086DE", "衣服", 1, "0.59", "0.150", "11.800"]
    assert [cell.value for cell in inbound[3]] == [None, "CP147905449DE", "鞋", 1, "0.59", None, None]


def test_customs_export_outputs_notify_party_only_when_different() -> None:
    same_notify = SimpleNamespace(
        name="ALLINE BV",
        address="Capronilaan 37 Schiphol-Rijk the Netherlands 1119 NG",
        email="import@alline.global",
        phone="+31 629 809 005",
        tax_info="VAT number: NL863476971B01",
        enabled=True,
    )
    contact = _make_waybill().consignee_contact
    contact.notify_party = same_notify
    workbook = _load_export(_make_service([]).build_waybill_export(_make_waybill(consignee_contact=contact)))
    labels = [row[0].value for row in workbook["提单资料"].iter_rows(min_row=1, max_col=2)]
    assert "通知人" not in labels

    different_contact = _make_waybill().consignee_contact
    different_contact.notify_party = SimpleNamespace(
        name="Notify BV",
        address="Other address",
        email="notify@example.com",
        phone="123",
        tax_info="EORI:NL123",
        enabled=True,
    )
    workbook = _load_export(_make_service([]).build_waybill_export(_make_waybill(consignee_contact=different_contact)))
    rows = {row[0].value: row[1].value for row in workbook["提单资料"].iter_rows(min_row=1, max_col=2)}
    assert "通知人" in rows
    assert "Notify BV" in rows["通知人"]
