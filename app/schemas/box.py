from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class BoxDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_path: str | None = None
    file_hash: str | None = None
    bound_waybill_id: int | None = None
    uploaded_by: int | None = None
    uploaded_at: datetime


class BoxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    box_no: str
    document_id: int | None = None
    current_waybill_id: int | None = None
    warehouse_waybill_no: str | None = None
    goods_name: str | None = None
    quantity: int | None = None
    weight: Decimal | None = None
    volume: Decimal | None = None
    weight_volume_ratio: Decimal | None = None
    source_row_number: int | None = None
    status: str
    raw_data: dict[str, Any]
    document: BoxDocumentOut | None = None
    created_at: datetime
    updated_at: datetime


class WarehouseFileImportError(BaseModel):
    row_number: int
    message: str


class WarehouseFileUploadResult(BaseModel):
    file_name: str
    warehouse_no: str
    document_id: int
    success_count: int
    skipped_count: int
    errors: list[WarehouseFileImportError]
