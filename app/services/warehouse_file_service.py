from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request
from app.models import AirWaybill, Box, BoxDocument, User
from app.repositories.box_repository import BoxRepository
from app.repositories.waybill_repository import WaybillRepository
from app.schemas.box import WarehouseFileImportError, WarehouseFileUploadResult
from app.services.permission_service import PermissionService


REQUIRED_COLUMNS = {
    "outer_barcode": {"外箱条码", "箱号", "外箱号", "box_no", "box no", "barcode"},
    "warehouse_waybill_no": {"提单号码", "提单号", "仓库提单号", "warehouse waybill no"},
    "goods_name": {"品名", "货物品名", "goods_name", "goods name", "cargo name"},
    "quantity": {"数量", "件数", "qty", "quantity"},
    "weight": {"重量", "收货重量", "weight", "weight kg"},
    "volume": {"收货体积信息", "体积", "方数", "volume", "volume cbm"},
}

DECIMAL_001 = Decimal("0.001")


@dataclass
class ParsedWarehouseBox:
    box_no: str
    warehouse_waybill_no: str | None
    goods_name: str | None
    quantity: int
    weight: Decimal
    volume: Decimal
    weight_volume_ratio: Decimal
    source_row_number: int
    raw_data: dict[str, Any]


@dataclass
class WarehouseFileParseResult:
    boxes: list[ParsedWarehouseBox]
    skipped_count: int
    errors: list[WarehouseFileImportError]


class WarehouseFileService:
    def __init__(self, db: Session):
        self.db = db
        self.boxes = BoxRepository(db)
        self.waybills = WaybillRepository(db)

    def list_boxes(self, waybill_id: int) -> list[Box]:
        return self.boxes.list_by_waybill(waybill_id)

    def upload_for_waybill(
        self,
        waybill_id: int,
        file_name: str,
        content: bytes,
        current_user: User,
    ) -> WarehouseFileUploadResult:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.waybills.get(waybill_id)
        if waybill is None:
            raise bad_request("waybill_not_found")

        parse_result = parse_warehouse_xlsx(file_name, content)
        if not parse_result.boxes:
            raise bad_request("warehouse_file_no_valid_rows")

        file_hash = hashlib.sha256(content).hexdigest()
        stored_path = self._store_file(file_name, file_hash, content)
        warehouse_no = Path(file_name).stem[:128]

        document = self.boxes.add_document(
            BoxDocument(
                file_name=file_name,
                file_path=str(stored_path),
                file_hash=file_hash,
                bound_waybill_id=waybill_id,
                uploaded_by=current_user.id,
            )
        )

        self.boxes.delete_by_waybill(waybill_id)
        self.boxes.add_boxes(
            [
                Box(
                    box_no=item.box_no,
                    document_id=document.id,
                    current_waybill_id=waybill_id,
                    warehouse_waybill_no=item.warehouse_waybill_no,
                    goods_name=item.goods_name,
                    quantity=item.quantity,
                    weight=item.weight,
                    volume=item.volume,
                    weight_volume_ratio=item.weight_volume_ratio,
                    source_row_number=item.source_row_number,
                    status="bound",
                    raw_data=item.raw_data,
                )
                for item in parse_result.boxes
            ]
        )
        waybill.warehouse_no = warehouse_no
        waybill.updated_by = current_user.id
        self.db.commit()

        return WarehouseFileUploadResult(
            file_name=file_name,
            warehouse_no=warehouse_no,
            document_id=document.id,
            success_count=len(parse_result.boxes),
            skipped_count=parse_result.skipped_count,
            errors=parse_result.errors,
        )

    def _store_file(self, file_name: str, file_hash: str, content: bytes) -> Path:
        storage_dir = Path(settings.warehouse_file_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file_name).suffix.lower()
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(file_name).stem).strip("._") or "warehouse-file"
        path = storage_dir / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_hash[:12]}_{safe_name}{suffix}"
        path.write_bytes(content)
        return path


def parse_warehouse_xlsx(file_name: str, content: bytes) -> WarehouseFileParseResult:
    if Path(file_name).suffix.lower() != ".xlsx":
        raise bad_request("warehouse_file_only_xlsx_supported")
    if not content:
        raise bad_request("warehouse_file_empty")

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise bad_request("warehouse_file_invalid_xlsx") from exc

    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    header_row_number = 0
    header_values: list[Any] = []
    for row_number, row in enumerate(rows, start=1):
        if any(_clean_text(value) for value in row):
            header_row_number = row_number
            header_values = list(row)
            break
    if not header_values:
        raise bad_request("warehouse_file_missing_header")

    column_map = _build_column_map(header_values)
    missing = [field for field in REQUIRED_COLUMNS if field not in column_map]
    if missing:
        raise bad_request(f"warehouse_file_missing_columns:{','.join(missing)}")

    boxes: list[ParsedWarehouseBox] = []
    errors: list[WarehouseFileImportError] = []
    skipped_count = 0
    normalized_headers = [_clean_text(value) or f"column_{idx + 1}" for idx, value in enumerate(header_values)]

    for row_number, row in enumerate(rows, start=header_row_number + 1):
        values = list(row)
        if not any(_clean_text(value) for value in values):
            skipped_count += 1
            continue

        raw_data = {
            normalized_headers[idx]: _raw_json_value(values[idx] if idx < len(values) else None)
            for idx in range(len(normalized_headers))
        }
        try:
            box_no = _required_text(values, column_map["outer_barcode"], "外箱条码")
            warehouse_waybill_no = _optional_text(values, column_map["warehouse_waybill_no"])
            goods_name = _optional_text(values, column_map["goods_name"])
            quantity = _parse_quantity(values, column_map["quantity"])
            weight = _parse_decimal_cell(values, column_map["weight"], "重量")
            volume = _parse_decimal_cell(values, column_map["volume"], "收货体积信息")
            if volume <= 0:
                raise ValueError("收货体积信息必须大于 0")
            ratio = (weight / volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        except ValueError as exc:
            errors.append(WarehouseFileImportError(row_number=row_number, message=str(exc)))
            continue

        boxes.append(
            ParsedWarehouseBox(
                box_no=box_no,
                warehouse_waybill_no=warehouse_waybill_no,
                goods_name=goods_name,
                quantity=quantity,
                weight=weight,
                volume=volume,
                weight_volume_ratio=ratio,
                source_row_number=row_number,
                raw_data=raw_data,
            )
        )

    return WarehouseFileParseResult(boxes=boxes, skipped_count=skipped_count, errors=errors)


def _build_column_map(header_values: list[Any]) -> dict[str, int]:
    normalized = [_normalize_header(value) for value in header_values]
    column_map: dict[str, int] = {}
    for field, aliases in REQUIRED_COLUMNS.items():
        normalized_aliases = {_normalize_header(alias) for alias in aliases}
        for index, header in enumerate(normalized):
            if header in normalized_aliases:
                column_map[field] = index
                break
    return column_map


def _normalize_header(value: Any) -> str:
    return re.sub(r"\s+", "", _clean_text(value).lower())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _value_at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _required_text(values: list[Any], index: int, label: str) -> str:
    value = _optional_text(values, index)
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _optional_text(values: list[Any], index: int) -> str | None:
    value = _clean_text(_value_at(values, index))
    return value or None


def _parse_quantity(values: list[Any], index: int) -> int:
    raw = _value_at(values, index)
    decimal = _to_decimal(raw, "数量")
    if decimal <= 0:
        raise ValueError("数量必须大于 0")
    if decimal != decimal.to_integral_value():
        raise ValueError("数量必须是整数")
    return int(decimal)


def _parse_decimal_cell(values: list[Any], index: int, label: str) -> Decimal:
    decimal = _to_decimal(_value_at(values, index), label)
    if decimal < 0:
        raise ValueError(f"{label}不能小于 0")
    return decimal.quantize(DECIMAL_001, rounding=ROUND_HALF_UP)


def _to_decimal(value: Any, label: str) -> Decimal:
    if value is None or _clean_text(value) == "":
        raise ValueError(f"{label}不能为空")
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        raw = str(value)
    else:
        text = _clean_text(value).replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            raise ValueError(f"{label}必须是有效数字")
        raw = match.group(0)
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label}必须是有效数字") from exc


def _raw_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
