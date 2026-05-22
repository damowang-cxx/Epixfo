from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request
from app.models import AirWaybill, Box, BoxDocument, BoxItem, User, WarehouseReceipt
from app.repositories.box_repository import BoxRepository
from app.repositories.waybill_repository import WaybillRepository
from app.schemas.box import (
    BoxBatchOperationResult,
    BoxCreate,
    BoxVolumeRecalculationResult,
    WarehouseBoxConflict,
    WarehouseFileImportError,
    WarehouseFileUploadResult,
)
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
DIMENSION_VOLUME_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\*|x|X|×)\s*(\d+(?:\.\d+)?)\s*(?:\*|x|X|×)\s*(\d+(?:\.\d+)?)"
)


@dataclass
class ParsedWarehouseBoxItem:
    warehouse_waybill_no: str | None
    goods_name: str | None
    quantity: int
    weight: Decimal
    source_row_number: int
    raw_data: dict[str, Any]


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
    items: list[ParsedWarehouseBoxItem]


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

    def list_unbound_boxes(self, *, page: int, page_size: int) -> tuple[list[Box], int, int, int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        items, total = self.boxes.list_unbound(page=page, page_size=page_size)
        return items, total, page, page_size

    def update_box_no(self, waybill_id: int, box_id: int, box_no: str, current_user: User) -> Box:
        """向后兼容：旧调用方仍可只改 box_no。"""
        return self.update_box(waybill_id, box_id, current_user, box_no=box_no)

    def update_box(
        self,
        waybill_id: int,
        box_id: int,
        current_user: User,
        *,
        box_no: str | None = None,
        is_general_cargo: bool | None = None,
    ) -> Box:
        """部分更新：仅设置传入的非 None 字段。"""
        PermissionService.assert_waybill_write(current_user)
        if self.waybills.get(waybill_id) is None:
            raise bad_request("waybill_not_found")
        box = self.boxes.get_by_waybill(waybill_id, box_id)
        if box is None:
            raise bad_request("box_not_found")

        if box_no is not None:
            cleaned_box_no = box_no.strip()
            if not cleaned_box_no:
                raise bad_request("box_no_required")
            existing = self.boxes.get_by_box_no(cleaned_box_no)
            if existing is not None and existing.id != box.id:
                raise bad_request("box_no_exists")
            box.box_no = cleaned_box_no

        if is_general_cargo is not None:
            box.is_general_cargo = is_general_cargo

        self.db.commit()
        self.db.refresh(box)
        return box

    def create_box(self, waybill_id: int, payload: BoxCreate, current_user: User) -> Box:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.waybills.get(waybill_id)
        if waybill is None:
            raise bad_request("waybill_not_found")
        warehouse_no = (waybill.warehouse_no or "").strip()
        if not warehouse_no:
            raise bad_request("target_warehouse_no_required")

        cleaned_box_no = (payload.box_no or "").strip()
        if not cleaned_box_no:
            raise bad_request("box_no_required")
        if self.boxes.get_by_box_no(cleaned_box_no) is not None:
            raise bad_request("box_no_exists")

        receipt = self._ensure_receipt(warehouse_no, waybill, document=None, current_user=current_user)
        weight = payload.weight.quantize(DECIMAL_001, rounding=ROUND_HALF_UP) if payload.weight is not None else None
        volume = payload.volume.quantize(DECIMAL_001, rounding=ROUND_HALF_UP) if payload.volume is not None else None
        weight_volume_ratio = (
            (weight / volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
            if weight is not None and volume is not None and volume > 0
            else (Decimal("0.000") if weight is not None or volume is not None else None)
        )

        box = Box(
            box_no=cleaned_box_no,
            warehouse_receipt_id=receipt.id,
            current_waybill_id=waybill.id,
            warehouse_waybill_no=payload.warehouse_waybill_no,
            goods_name=payload.goods_name,
            quantity=payload.quantity,
            weight=weight,
            volume=volume,
            weight_volume_ratio=weight_volume_ratio,
            is_general_cargo=payload.is_general_cargo,
            status="bound",
            raw_data={"source": "manual"},
        )
        self.db.add(box)
        self.db.flush()

        has_item_data = any(
            value not in (None, "")
            for value in (payload.warehouse_waybill_no, payload.goods_name, payload.quantity, weight)
        )
        if has_item_data:
            self.boxes.add_items(
                [
                    BoxItem(
                        box_id=box.id,
                        warehouse_waybill_no=payload.warehouse_waybill_no,
                        goods_name=payload.goods_name,
                        quantity=payload.quantity,
                        weight=weight,
                        raw_data={"source": "manual"},
                    )
                ]
            )

        self._refresh_receipt_totals(receipt)
        self.db.commit()
        self.db.refresh(box)
        return box

    def delete_box(self, waybill_id: int, box_id: int, current_user: User) -> None:
        PermissionService.assert_waybill_write(current_user)
        if self.waybills.get(waybill_id) is None:
            raise bad_request("waybill_not_found")
        box = self.boxes.get_by_waybill(waybill_id, box_id)
        if box is None:
            raise bad_request("box_not_found")
        receipt = box.warehouse_receipt
        self.db.delete(box)
        self.db.flush()
        self._refresh_receipt_totals(receipt)
        self.db.commit()

    def recalculate_box_volumes(self, waybill_id: int, current_user: User) -> BoxVolumeRecalculationResult:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.waybills.get(waybill_id)
        if waybill is None:
            raise bad_request("waybill_not_found")
        booked_volume = waybill.booked_volume
        if booked_volume is None or booked_volume <= 0:
            raise bad_request("booked_volume_required")

        boxes = self.boxes.list_by_waybill(waybill_id)
        if not boxes:
            raise bad_request("warehouse_boxes_required")

        booked_volume = booked_volume.quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        old_total_volume = sum((item.volume or Decimal("0.000") for item in boxes), Decimal("0.000")).quantize(
            DECIMAL_001,
            rounding=ROUND_HALF_UP,
        )
        total_weight = sum((item.weight or Decimal("0.000") for item in boxes), Decimal("0.000")).quantize(
            DECIMAL_001,
            rounding=ROUND_HALF_UP,
        )
        if old_total_volume <= 0:
            raise bad_request("warehouse_volume_required")
        if old_total_volume <= booked_volume:
            return BoxVolumeRecalculationResult(
                booked_volume=booked_volume,
                total_weight=total_weight,
                old_total_volume=old_total_volume,
                new_total_volume=old_total_volume,
                adjusted=False,
                boxes=boxes,
            )

        excess_volume = (old_total_volume - booked_volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        if excess_volume > Decimal("1.000"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "warehouse_volume_exceeds_booking",
                    "message": "入仓箱数超出订舱方数，请移除部分箱。",
                    "booked_volume": str(booked_volume),
                    "total_volume": str(old_total_volume),
                    "excess_volume": str(excess_volume),
                },
            )

        scaled_volumes = _scale_box_volumes_to_target(boxes, booked_volume, old_total_volume)
        ratio = booked_volume / old_total_volume
        recalculated_at = datetime.now(UTC).isoformat()
        touched_receipt_ids = {box.warehouse_receipt_id for box in boxes if box.warehouse_receipt_id is not None}
        for box in boxes:
            old_volume = box.volume or Decimal("0.000")
            new_volume = scaled_volumes.get(box.id, Decimal("0.000"))
            box.volume = new_volume
            box.weight_volume_ratio = (
                ((box.weight or Decimal("0.000")) / new_volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
                if new_volume > 0
                else Decimal("0.000")
            )
            raw_data = dict(box.raw_data or {})
            raw_data["volume_recalculation"] = {
                "source": "booked_volume_fit",
                "old_volume": str(old_volume.quantize(DECIMAL_001, rounding=ROUND_HALF_UP)),
                "new_volume": str(new_volume),
                "old_total_volume": str(old_total_volume),
                "booked_volume": str(booked_volume),
                "ratio": str(ratio.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
                "recalculated_at": recalculated_at,
            }
            box.raw_data = raw_data

        for receipt_id in touched_receipt_ids:
            self._refresh_receipt_totals(self.boxes.get_receipt_by_id(receipt_id))
        self.db.commit()
        updated_boxes = self.boxes.list_by_waybill(waybill_id)
        new_total_volume = sum((item.volume or Decimal("0.000") for item in updated_boxes), Decimal("0.000")).quantize(
            DECIMAL_001,
            rounding=ROUND_HALF_UP,
        )
        return BoxVolumeRecalculationResult(
            booked_volume=booked_volume,
            total_weight=total_weight,
            old_total_volume=old_total_volume,
            new_total_volume=new_total_volume,
            adjusted=True,
            boxes=updated_boxes,
        )

    def upload_for_waybill(
        self,
        waybill_id: int,
        file_name: str,
        content: bytes,
        current_user: User,
        force_move_box_nos: list[str] | None = None,
        skip_conflict_box_nos: list[str] | None = None,
    ) -> WarehouseFileUploadResult:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.waybills.get(waybill_id)
        if waybill is None:
            raise bad_request("waybill_not_found")

        parse_result = parse_warehouse_xlsx(file_name, content)
        if not parse_result.boxes:
            raise bad_request(_format_no_valid_rows_error(parse_result.errors))

        warehouse_no = Path(file_name).stem[:128]
        if not warehouse_no:
            raise bad_request("warehouse_no_required")

        forced_box_nos = {item.strip() for item in force_move_box_nos or [] if item and item.strip()}
        skipped_conflict_box_nos = {item.strip() for item in skip_conflict_box_nos or [] if item and item.strip()}
        conflicts = self._upload_conflicts(parse_result.boxes, waybill, warehouse_no, forced_box_nos)
        conflicts = [item for item in conflicts if item.box_no not in skipped_conflict_box_nos]
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "warehouse_box_conflicts",
                    "message": "部分外箱条码已绑定到其他提单入仓号",
                    "conflicts": [item.model_dump() for item in conflicts],
                },
            )

        bindable_boxes = [item for item in parse_result.boxes if item.box_no not in skipped_conflict_box_nos]
        if not bindable_boxes:
            raise bad_request("warehouse_file_no_bindable_boxes")

        file_hash = hashlib.sha256(content).hexdigest()
        stored_path = self._store_file(file_name, file_hash, content)

        document = self.boxes.add_document(
            BoxDocument(
                file_name=file_name,
                file_path=str(stored_path),
                file_hash=file_hash,
                bound_waybill_id=waybill_id,
                uploaded_by=current_user.id,
            )
        )

        receipt = self._ensure_receipt(warehouse_no, waybill, document=document, current_user=current_user)
        self._unbind_previous_waybill_receipt_if_needed(waybill, warehouse_no)
        touched_receipt_ids = self._sync_receipt_boxes(receipt, waybill, document, bindable_boxes)
        waybill.warehouse_no = warehouse_no
        waybill.updated_by = current_user.id
        self._refresh_receipt_totals(receipt)
        for receipt_id in touched_receipt_ids:
            if receipt_id != receipt.id:
                self._refresh_receipt_totals(self.boxes.get_receipt_by_id(receipt_id))
        self.db.commit()

        return WarehouseFileUploadResult(
            file_name=file_name,
            warehouse_no=warehouse_no,
            document_id=document.id,
            success_count=len(bindable_boxes),
            skipped_count=parse_result.skipped_count,
            errors=parse_result.errors,
        )

    def batch_bind_boxes(self, box_ids: list[int], target_waybill_id: int, current_user: User) -> BoxBatchOperationResult:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.waybills.get(target_waybill_id)
        if waybill is None:
            raise bad_request("target_waybill_not_found")
        if not waybill.warehouse_no:
            raise bad_request("target_warehouse_no_required")
        boxes = self._load_boxes_for_batch(box_ids)
        receipt = self._ensure_receipt(waybill.warehouse_no, waybill, document=None, current_user=current_user)
        touched_receipt_ids = {box.warehouse_receipt_id for box in boxes if box.warehouse_receipt_id is not None}
        for box in boxes:
            box.warehouse_receipt_id = receipt.id
            box.current_waybill_id = waybill.id
            box.status = "bound"
        self._refresh_receipt_totals(receipt)
        for receipt_id in touched_receipt_ids:
            if receipt_id != receipt.id:
                self._refresh_receipt_totals(self.boxes.get_receipt_by_id(receipt_id))
        self.db.commit()
        return BoxBatchOperationResult(updated_count=len(boxes), boxes=self.boxes.list_by_ids([box.id for box in boxes]))

    def batch_unbind_boxes(self, box_ids: list[int], current_user: User) -> BoxBatchOperationResult:
        PermissionService.assert_waybill_write(current_user)
        boxes = self._load_boxes_for_batch(box_ids)
        touched_receipt_ids = {box.warehouse_receipt_id for box in boxes if box.warehouse_receipt_id is not None}
        for box in boxes:
            box.warehouse_receipt_id = None
            box.current_waybill_id = None
            box.status = "unbound"
        for receipt_id in touched_receipt_ids:
            self._refresh_receipt_totals(self.boxes.get_receipt_by_id(receipt_id))
        self.db.commit()
        return BoxBatchOperationResult(updated_count=len(boxes), boxes=self.boxes.list_by_ids([box.id for box in boxes]))

    def _load_boxes_for_batch(self, box_ids: list[int]) -> list[Box]:
        unique_ids = list(dict.fromkeys(box_ids))
        boxes = self.boxes.list_by_ids(unique_ids)
        if len(boxes) != len(unique_ids):
            raise bad_request("box_not_found")
        return boxes

    def _upload_conflicts(
        self,
        parsed_boxes: list[ParsedWarehouseBox],
        target_waybill: AirWaybill,
        target_warehouse_no: str,
        forced_box_nos: set[str],
    ) -> list[WarehouseBoxConflict]:
        parsed_box_nos = [item.box_no for item in parsed_boxes]
        conflicts: list[WarehouseBoxConflict] = []
        for box, current_waybill, current_receipt in self.boxes.list_conflicting_boxes(parsed_box_nos, target_warehouse_no):
            if box.box_no in forced_box_nos:
                continue
            conflicts.append(
                WarehouseBoxConflict(
                    box_no=box.box_no,
                    current_waybill_id=current_waybill.id if current_waybill else None,
                    current_waybill_no=current_waybill.waybill_no if current_waybill else None,
                    current_warehouse_no=current_receipt.warehouse_no if current_receipt else None,
                    target_waybill_id=target_waybill.id,
                    target_waybill_no=target_waybill.waybill_no,
                    target_warehouse_no=target_warehouse_no,
                )
            )
        return conflicts

    def _ensure_receipt(
        self,
        warehouse_no: str,
        waybill: AirWaybill,
        *,
        document: BoxDocument | None,
        current_user: User,
    ) -> WarehouseReceipt:
        receipt = self.boxes.get_receipt_by_warehouse_no(warehouse_no)
        if receipt is not None and receipt.waybill_id not in (None, waybill.id):
            raise bad_request("warehouse_receipt_bound_to_other_waybill")
        if receipt is None:
            receipt = self.boxes.add_receipt(
                WarehouseReceipt(
                    warehouse_no=warehouse_no,
                    waybill_id=waybill.id,
                    source_document_id=document.id if document else None,
                    uploaded_by=current_user.id,
                    total_quantity=0,
                    total_weight=Decimal("0.000"),
                    total_volume=Decimal("0.000"),
                    weight_volume_ratio=Decimal("0.000"),
                )
            )
        else:
            receipt.waybill_id = waybill.id
            if document is not None:
                receipt.source_document_id = document.id
                receipt.uploaded_by = current_user.id
        return receipt

    def _unbind_previous_waybill_receipt_if_needed(self, waybill: AirWaybill, next_warehouse_no: str) -> None:
        if not waybill.warehouse_no or waybill.warehouse_no == next_warehouse_no:
            return
        previous = self.boxes.get_receipt_by_warehouse_no(waybill.warehouse_no)
        if previous is None or previous.waybill_id != waybill.id:
            return
        previous_boxes = self.boxes.list_by_receipt_id(previous.id)
        for box in previous_boxes:
            box.warehouse_receipt_id = None
            box.current_waybill_id = None
            box.status = "unbound"
        previous.waybill_id = None
        self._refresh_receipt_totals(previous)

    def _sync_receipt_boxes(
        self,
        receipt: WarehouseReceipt,
        waybill: AirWaybill,
        document: BoxDocument,
        parsed_boxes: list[ParsedWarehouseBox],
    ) -> set[int]:
        touched_receipt_ids: set[int] = set()
        parsed_by_no = {item.box_no: item for item in parsed_boxes}
        existing_in_receipt = self.boxes.list_by_receipt_id(receipt.id)
        for existing in existing_in_receipt:
            if existing.box_no not in parsed_by_no:
                if existing.warehouse_receipt_id is not None:
                    touched_receipt_ids.add(existing.warehouse_receipt_id)
                existing.warehouse_receipt_id = None
                existing.current_waybill_id = None
                existing.status = "unbound"

        existing_by_no = {box.box_no: box for box in self.boxes.list_by_box_nos(list(parsed_by_no))}
        for parsed in parsed_boxes:
            box = existing_by_no.get(parsed.box_no)
            if box is None:
                box = Box(box_no=parsed.box_no)
                self.db.add(box)
                self.db.flush()
            elif box.warehouse_receipt_id is not None:
                touched_receipt_ids.add(box.warehouse_receipt_id)
            box.document_id = document.id
            box.warehouse_receipt_id = receipt.id
            box.current_waybill_id = waybill.id
            box.warehouse_waybill_no = parsed.warehouse_waybill_no
            box.goods_name = parsed.goods_name
            box.quantity = parsed.quantity
            box.weight = parsed.weight
            box.volume = parsed.volume
            box.weight_volume_ratio = parsed.weight_volume_ratio
            box.source_row_number = parsed.source_row_number
            box.status = "bound"
            box.raw_data = parsed.raw_data
            self.db.flush()

            self.boxes.delete_items_for_box(box.id)
            self.boxes.add_items(
                [
                    BoxItem(
                        box_id=box.id,
                        document_id=document.id,
                        warehouse_waybill_no=item.warehouse_waybill_no,
                        goods_name=item.goods_name,
                        quantity=item.quantity,
                        weight=item.weight,
                        source_row_number=item.source_row_number,
                        raw_data=item.raw_data,
                    )
                    for item in parsed.items
                ]
            )
        return touched_receipt_ids

    def _refresh_receipt_totals(self, receipt: WarehouseReceipt | None) -> None:
        if receipt is None:
            return
        boxes = self.boxes.list_by_receipt_id(receipt.id)
        total_quantity = sum(item.quantity or 0 for item in boxes)
        total_weight = sum((item.weight or Decimal("0.000") for item in boxes), Decimal("0.000"))
        total_volume = sum((item.volume or Decimal("0.000") for item in boxes), Decimal("0.000"))
        receipt.total_quantity = total_quantity
        receipt.total_weight = total_weight.quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        receipt.total_volume = total_volume.quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        receipt.weight_volume_ratio = (
            (receipt.total_weight / receipt.total_volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
            if receipt.total_volume and receipt.total_volume > 0
            else Decimal("0.000")
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

    boxes_by_no: dict[str, ParsedWarehouseBox] = {}
    box_order: list[str] = []
    errors: list[WarehouseFileImportError] = []
    skipped_count = 0
    normalized_headers = [_clean_text(value) or f"column_{idx + 1}" for idx, value in enumerate(header_values)]
    current_box_no: str | None = None

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
            raw_box_no = _optional_text(values, column_map["outer_barcode"])
            if raw_box_no:
                current_box_no = raw_box_no
            if not current_box_no:
                raise ValueError("外箱条码不能为空")
            box_no = current_box_no
            is_continuation_row = raw_box_no is None
            warehouse_waybill_no = _optional_text(values, column_map["warehouse_waybill_no"])
            goods_name = _optional_text(values, column_map["goods_name"])
            quantity = _parse_quantity(values, column_map["quantity"])
            weight = _parse_decimal_cell(values, column_map["weight"], "重量")
            volume = _parse_volume_cell(values, column_map["volume"], allow_empty=is_continuation_row)
            if not is_continuation_row and volume <= 0:
                raise ValueError("收货体积信息必须大于 0")
        except ValueError as exc:
            errors.append(WarehouseFileImportError(row_number=row_number, message=str(exc)))
            continue

        item = ParsedWarehouseBoxItem(
            warehouse_waybill_no=warehouse_waybill_no,
            goods_name=goods_name,
            quantity=quantity,
            weight=weight,
            source_row_number=row_number,
            raw_data=raw_data,
        )
        parsed_box = boxes_by_no.get(box_no)
        if parsed_box is None:
            parsed_box = ParsedWarehouseBox(
                box_no=box_no,
                warehouse_waybill_no=warehouse_waybill_no,
                goods_name=goods_name,
                quantity=0,
                weight=Decimal("0.000"),
                volume=volume,
                weight_volume_ratio=Decimal("0.000"),
                source_row_number=row_number,
                raw_data=raw_data,
                items=[],
            )
            boxes_by_no[box_no] = parsed_box
            box_order.append(box_no)

        parsed_box.items.append(item)
        parsed_box.quantity += quantity
        parsed_box.weight = (parsed_box.weight + weight).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
        if parsed_box.volume <= 0 and volume > 0:
            parsed_box.volume = volume
        if parsed_box.warehouse_waybill_no is None and warehouse_waybill_no:
            parsed_box.warehouse_waybill_no = warehouse_waybill_no
        if parsed_box.goods_name is None and goods_name:
            parsed_box.goods_name = goods_name
        parsed_box.weight_volume_ratio = (
            (parsed_box.weight / parsed_box.volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
            if parsed_box.volume > 0
            else Decimal("0.000")
        )

    return WarehouseFileParseResult(boxes=[boxes_by_no[box_no] for box_no in box_order], skipped_count=skipped_count, errors=errors)


def _scale_box_volumes_to_target(boxes: list[Box], target_volume: Decimal, current_total_volume: Decimal) -> dict[int, Decimal]:
    positive_boxes = [box for box in boxes if (box.volume or Decimal("0.000")) > 0]
    if not positive_boxes:
        return {box.id: Decimal("0.000") for box in boxes}

    ratio = target_volume / current_total_volume
    scaled_rows: list[tuple[Box, Decimal, Decimal]] = []
    floor_sum = Decimal("0.000")
    for box in positive_boxes:
        raw = (box.volume or Decimal("0.000")) * ratio
        floored = raw.quantize(DECIMAL_001, rounding=ROUND_DOWN)
        scaled_rows.append((box, floored, raw - floored))
        floor_sum += floored

    remainder_units = int(((target_volume - floor_sum) / DECIMAL_001).to_integral_value(rounding=ROUND_DOWN))
    scaled_rows.sort(key=lambda item: item[2], reverse=True)
    result = {box.id: Decimal("0.000") for box in boxes}
    for index, (box, floored, _fraction) in enumerate(scaled_rows):
        increment = DECIMAL_001 if index < remainder_units else Decimal("0.000")
        result[box.id] = (floored + increment).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
    return result


def _format_no_valid_rows_error(errors: list[WarehouseFileImportError]) -> str:
    if not errors:
        return "warehouse_file_no_valid_rows"
    details = "；".join(f"第 {item.row_number} 行（{item.message}）" for item in errors[:5])
    suffix = f"；另 {len(errors) - 5} 行" if len(errors) > 5 else ""
    return f"没有有效货物行，失败行：{details}{suffix}"


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


def _parse_volume_cell(values: list[Any], index: int, allow_empty: bool = False) -> Decimal:
    raw = _value_at(values, index)
    if raw is None or _clean_text(raw) == "":
        if allow_empty:
            return Decimal("0.000")
        raise ValueError("收货体积信息不能为空")

    text = _clean_text(raw).replace(",", "")
    dimension_match = DIMENSION_VOLUME_PATTERN.search(text)
    if dimension_match:
        length, width, height = (Decimal(part) for part in dimension_match.groups())
        decimal = length * width * height / Decimal("1000000")
    else:
        decimal = _to_decimal(raw, "收货体积信息")

    if decimal < 0:
        raise ValueError("收货体积信息不能小于 0")
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
