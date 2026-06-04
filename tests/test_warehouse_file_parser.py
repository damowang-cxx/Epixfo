from decimal import Decimal
from io import BytesIO

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.services.warehouse_file_service import parse_warehouse_xlsx


def _xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_parse_warehouse_xlsx_success_and_calculates_ratio() -> None:
    content = _xlsx_bytes(
        [
            ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息", "收货重量/方"],
            ["BOX-001", "WH-AWB-001", "Shoes", 2, 10, 4, "ignored"],
            ["BOX-002", "WH-AWB-002", "Bags", "3", "7.5 KG", "2.5 CBM", "ignored"],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert len(result.boxes) == 2
    assert result.errors == []
    assert [(cell.row_number, cell.box_no) for cell in result.barcode_cells] == [(2, "BOX-001"), (3, "BOX-002")]
    assert result.boxes[0].box_no == "BOX-001"
    assert result.boxes[0].warehouse_waybill_no == "WH-AWB-001"
    assert result.boxes[0].quantity == 2
    assert str(result.boxes[0].weight) == "10.000"
    assert result.boxes[0].original_volume_info == "4"
    assert result.boxes[0].original_weight_volume_ratio == "ignored"
    assert str(result.boxes[0].volume) == "4.000"
    assert str(result.boxes[0].weight_volume_ratio) == "2.500"
    assert result.boxes[1].goods_name == "Bags"
    assert str(result.boxes[1].weight_volume_ratio) == "3.000"


def test_parse_warehouse_xlsx_accepts_traditional_chinese_headers() -> None:
    content = _xlsx_bytes(
        [
            ["外箱條碼", "提單號碼", "品名", "數量", "重量", "收貨體積信息", "收貨重量/方"],
            ["BOX-TW-001", "WH-TW-001", "Shoes", 4, 12, "60*50*40", "0.120"],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert result.errors == []
    assert len(result.boxes) == 1
    assert result.boxes[0].box_no == "BOX-TW-001"
    assert result.boxes[0].warehouse_waybill_no == "WH-TW-001"
    assert result.boxes[0].quantity == 4
    assert result.boxes[0].original_volume_info == "60*50*40"
    assert result.boxes[0].original_weight_volume_ratio == "0.120"
    assert result.boxes[0].volume == Decimal("0.120")


def test_parse_warehouse_xlsx_allows_missing_quantity_column() -> None:
    content = _xlsx_bytes(
        [
            ["box_no", "warehouse waybill no", "goods_name", "weight", "volume"],
            ["BOX-NO-QTY", "WH-NO-QTY", "Shoes", 12, "60*50*40"],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert result.errors == []
    assert len(result.boxes) == 1
    assert result.boxes[0].box_no == "BOX-NO-QTY"
    assert result.boxes[0].quantity is None
    assert result.boxes[0].items[0].quantity is None
    assert str(result.boxes[0].weight) == "12.000"
    assert str(result.boxes[0].volume) == "0.120"


def test_parse_warehouse_xlsx_allows_empty_quantity_cell() -> None:
    content = _xlsx_bytes(
        [
            ["box_no", "warehouse waybill no", "goods_name", "quantity", "weight", "volume"],
            ["BOX-EMPTY-QTY", "WH-EMPTY-QTY", "Shoes", "", 12, "60*50*40"],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert result.errors == []
    assert result.boxes[0].quantity is None
    assert result.boxes[0].items[0].quantity is None


def test_parse_warehouse_xlsx_rejects_non_xlsx() -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_warehouse_xlsx("warehouse.csv", b"not excel")

    assert exc_info.value.detail == "warehouse_file_only_xlsx_supported"


def test_parse_warehouse_xlsx_rejects_missing_required_header() -> None:
    content = _xlsx_bytes([["外箱条码", "品名", "数量", "重量", "收货体积信息"]])

    with pytest.raises(HTTPException) as exc_info:
        parse_warehouse_xlsx("warehouse.xlsx", content)

    assert "warehouse_file_missing_columns" in exc_info.value.detail


def test_parse_warehouse_xlsx_collects_invalid_rows() -> None:
    content = _xlsx_bytes(
        [
            ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息"],
            ["", "WH-AWB-001", "Shoes", 2, 10, 4],
            ["BOX-002", "WH-AWB-002", "Bags", 1, 8, 2],
            ["", "WH-AWB-002-B", "Bags", 1, 3, ""],
            ["BOX-003", "WH-AWB-003", "Hats", 1.5, 8, 2],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert len(result.boxes) == 1
    assert result.boxes[0].box_no == "BOX-002"
    assert len(result.boxes[0].items) == 2
    assert result.boxes[0].items[1].warehouse_waybill_no == "WH-AWB-002-B"
    assert result.boxes[0].quantity == 2
    assert str(result.boxes[0].weight) == "11.000"
    assert str(result.boxes[0].volume) == "2.000"
    assert str(result.boxes[0].weight_volume_ratio) == "5.500"
    assert len(result.errors) == 2
    assert result.errors[0].row_number == 2
    assert "外箱条码" in result.errors[0].message
    assert result.errors[1].row_number == 5
    assert "数量必须是整数" in result.errors[1].message


def test_parse_warehouse_xlsx_inherits_box_no_and_converts_dimensions() -> None:
    content = _xlsx_bytes(
        [
            ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息", "收货重量/方"],
            ["DHLAE57762", "CP148017895DE", "长袖衬衫", 5, 0.64, "60*50*50", 0.15],
            ["", "CP147897504DE", "衣服", 5, 2.9, "", 0],
            ["", "CP148008978DE", "女式睡衣套装", 2, 1.21, "", 0],
            ["", "CP148027875DE", "鞋子，钱包", 2, 2.18, 0, 0],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert result.errors == []
    assert [item.box_no for item in result.boxes] == ["DHLAE57762"]
    assert len(result.boxes[0].items) == 4
    assert [item.warehouse_waybill_no for item in result.boxes[0].items] == [
        "CP148017895DE",
        "CP147897504DE",
        "CP148008978DE",
        "CP148027875DE",
    ]
    assert result.boxes[0].quantity == 14
    assert str(result.boxes[0].weight) == "6.930"
    assert result.boxes[0].original_volume_info == "60*50*50"
    assert result.boxes[0].original_weight_volume_ratio == "0.15"
    assert str(result.boxes[0].volume) == "0.150"
    assert str(result.boxes[0].weight_volume_ratio) == "46.200"


def test_parse_warehouse_xlsx_converts_semicolon_dimension_to_cbm() -> None:
    content = _xlsx_bytes(
        [
            ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息", "收货重量/方"],
            ["DPDD05445", "01505364502907", "长袖衬衫", 3, 18.67, "51*37*35;", 0.066],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert result.errors == []
    assert result.boxes[0].original_volume_info == "51*37*35;"
    assert result.boxes[0].original_weight_volume_ratio == "0.066"
    assert str(result.boxes[0].volume) == "0.066"
    assert str(result.boxes[0].weight_volume_ratio) == "282.879"


def test_parse_warehouse_xlsx_only_inherits_from_successfully_parsed_box() -> None:
    content = _xlsx_bytes(
        [
            ["外箱条码", "提单号码", "品名", "数量", "重量", "收货体积信息"],
            ["BOX-BAD", "WH-AWB-BAD", "Shoes", "not-int", 10, "40*40*40"],
            ["", "WH-AWB-SHOULD-FAIL", "Bags", 1, 2, ""],
            ["BOX-OK", "WH-AWB-OK", "Hats", 1, 3, "50*40*30"],
            ["", "WH-AWB-OK-2", "Socks", 2, 4, ""],
        ]
    )

    result = parse_warehouse_xlsx("warehouse.xlsx", content)

    assert [item.box_no for item in result.boxes] == ["BOX-OK"]
    assert len(result.boxes[0].items) == 2
    assert result.boxes[0].quantity == 3
    assert result.boxes[0].original_weight_volume_ratio is None
    assert str(result.boxes[0].weight) == "7.000"
    assert str(result.boxes[0].volume) == "0.060"
    assert [item.row_number for item in result.errors] == [2, 3]
    assert [(cell.row_number, cell.box_no) for cell in result.barcode_cells] == [(2, "BOX-BAD"), (4, "BOX-OK")]
    assert "数量必须是有效数字" in result.errors[0].message
    assert "外箱条码不能为空" in result.errors[1].message
