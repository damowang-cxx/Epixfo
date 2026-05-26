from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.services.waybill_bulk_import_service import WaybillImportTemplateParser


HEADERS = [
    "航代",
    "航班信息",
    "提单号",
    "入仓号",
    "收件人",
    "资料\n数据",
    "交货时间",
    "截单时间",
    "订舱重量",
    "方数",
    "密度",
    "报价",
    "",
    "入仓数据",
    "",
    "",
    "航司",
    "航程",
    "飞出时间",
    "到达时间",
    "通知提取",
    "提取时间",
    "",
    "备注",
    "航空费",
    "付款日期",
]


def _workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(HEADERS)
    for row in rows:
        worksheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_waybill_import_parser_maps_template_columns() -> None:
    content = _workbook_bytes(
        [
            [
                "WZ",
                "QR8943/01",
                "157-40742074",
                "AMS-IN-001",
                "BBV",
                "林",
                "",
                "CAN-PKX-AMS",
                "1000",
                "6",
                "1:167",
                "38.6-0.5=38.1",
                "含TC",
                "58",
                "893",
                "5.12",
                "",
                "",
                "",
                "",
                "通知",
                "",
                "",
                "BBV显示齐",
                "33686.8",
                "",
            ]
        ]
    )

    result = WaybillImportTemplateParser(
        agents_by_name={"wz": 9},
        consignees_by_name={"bbv": 18},
        users_by_name={"林": 7},
    ).parse(content)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.error is None
    payload = row.payload
    assert payload is not None
    assert payload.waybill_no == "157-40742074"
    assert payload.carrier_agent_id == 9
    assert payload.consignee_contact_id == 18
    assert payload.document_operator_id == 7
    assert payload.planned_flight_info == "QR8943/01"
    assert payload.planned_route_text == "CAN-PKX-AMS"
    assert payload.departure_port == "CAN"
    assert payload.destination_port == "AMS"
    assert payload.booked_weight == 1000
    assert payload.booked_volume == 6
    assert payload.density == 167
    assert payload.quotation == "38.6-0.5=38.1"
    assert payload.include_tc is True
    assert payload.notify_pickup is True
    assert payload.warehouse_data_remark == "58 / 893 / 5.12"
    assert str(payload.air_freight_cost) == "33686.8"
    assert payload.internal_remark and "BBV显示齐" in payload.internal_remark


def test_waybill_import_parser_reports_unmatched_required_names() -> None:
    content = _workbook_bytes(
        [
            [
                "UNKNOWN",
                "QR8943/01",
                "157-40742074",
                "",
                "BBV",
            ]
        ]
    )

    result = WaybillImportTemplateParser(consignees_by_name={"bbv": 18}).parse(content)

    assert len(result.rows) == 1
    assert result.rows[0].payload is None
    assert result.rows[0].error == "航代未匹配: UNKNOWN"


def test_waybill_import_parser_requires_template_headers() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["提单号"])
    buffer = BytesIO()
    workbook.save(buffer)

    with pytest.raises(HTTPException) as exc_info:
        WaybillImportTemplateParser().parse(buffer.getvalue())

    assert exc_info.value.detail == "waybill_import_header_not_found"
