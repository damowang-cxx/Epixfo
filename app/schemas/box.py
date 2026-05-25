from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BoxDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_path: str | None = None
    file_hash: str | None = None
    bound_waybill_id: int | None = None
    uploaded_by: int | None = None
    uploaded_at: datetime


class WarehouseReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warehouse_no: str
    waybill_id: int | None = None
    source_document_id: int | None = None
    uploaded_by: int | None = None
    total_quantity: int
    total_weight: Decimal | None = None
    total_volume: Decimal | None = None
    weight_volume_ratio: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class BoxItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    box_id: int
    document_id: int | None = None
    warehouse_waybill_no: str | None = None
    goods_name: str | None = None
    quantity: int | None = None
    weight: Decimal | None = None
    source_row_number: int | None = None
    raw_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BoxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    box_no: str
    document_id: int | None = None
    warehouse_receipt_id: int | None = None
    current_waybill_id: int | None = None
    warehouse_waybill_no: str | None = None
    goods_name: str | None = None
    quantity: int | None = None
    weight: Decimal | None = None
    original_volume_info: str | None = None
    original_weight_volume_ratio: str | None = None
    volume: Decimal | None = None
    weight_volume_ratio: Decimal | None = None
    source_row_number: int | None = None
    status: str
    is_general_cargo: bool = False
    never_bound_direct_upload: bool = False
    unbound_reason: str | None = None
    unbound_remark: str | None = None
    raw_data: dict[str, Any]
    document: BoxDocumentOut | None = None
    warehouse_receipt: WarehouseReceiptOut | None = None
    items: list[BoxItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BoxUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    box_no: str | None = Field(default=None, min_length=1, max_length=128)
    is_general_cargo: bool | None = None


class BoxCreate(BaseModel):
    """手动新增一条箱号记录（绕开 Excel 上传）。box_no 必填，其他可选。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    box_no: str = Field(min_length=1, max_length=128)
    warehouse_waybill_no: str | None = Field(default=None, max_length=128)
    goods_name: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    weight: Decimal | None = Field(default=None, ge=0)
    volume: Decimal | None = Field(default=None, ge=0)
    is_general_cargo: bool = False


class WarehouseFileImportError(BaseModel):
    row_number: int
    message: str


class WarehouseBoxConflict(BaseModel):
    box_no: str
    current_waybill_id: int | None = None
    current_waybill_no: str | None = None
    current_warehouse_no: str | None = None
    target_waybill_id: int
    target_waybill_no: str
    target_warehouse_no: str


class WarehouseFileUploadResult(BaseModel):
    file_name: str
    warehouse_no: str
    document_id: int
    success_count: int
    skipped_count: int
    errors: list[WarehouseFileImportError]
    conflicts: list[WarehouseBoxConflict] = Field(default_factory=list)


class BoxBatchBindRequest(BaseModel):
    box_ids: list[int] = Field(min_length=1)
    target_waybill_id: int


class BoxBatchUnbindRequest(BaseModel):
    box_ids: list[int] = Field(min_length=1)


class BoxBatchTransferRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    box_ids: list[int] = Field(min_length=1)
    target_type: Literal["waybill", "unbound"]
    target_waybill_id: int | None = None
    unbound_reason: Literal["customs_inspection", "other"] | None = None
    unbound_remark: str | None = None


class BoxBatchOperationResult(BaseModel):
    updated_count: int
    boxes: list[BoxOut]


class BoxVolumeRecalculationResult(BaseModel):
    booked_volume: Decimal
    total_weight: Decimal
    old_total_volume: Decimal
    new_total_volume: Decimal
    adjusted: bool
    boxes: list[BoxOut]
