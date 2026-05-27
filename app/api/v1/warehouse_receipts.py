from typing import Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.box import (
    BoxOut,
    WarehouseFileUploadResult,
    WarehouseReceiptBindRequest,
    WarehouseReceiptListOut,
)
from app.schemas.common import PageResponse
from app.services.permission_service import PermissionService
from app.services.warehouse_file_service import WarehouseFileService

router = APIRouter(prefix="/warehouse-receipts", tags=["warehouse-receipts"])


@router.get("", response_model=PageResponse[WarehouseReceiptListOut])
def list_warehouse_receipts(
    page: int = 1,
    page_size: int = 50,
    binding: Literal["all", "unbound"] = "all",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    items, total, page, page_size = WarehouseFileService(db).list_receipts(
        page=page,
        page_size=page_size,
        unbound_only=binding == "unbound",
    )
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/unbound", response_model=PageResponse[WarehouseReceiptListOut])
def list_unbound_warehouse_receipts(
    page: int = 1,
    page_size: int = 50,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    items, total, page, page_size = WarehouseFileService(db).list_receipts(
        page=page,
        page_size=page_size,
        unbound_only=True,
    )
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/unbound/warehouse-file", response_model=WarehouseFileUploadResult)
async def upload_unbound_warehouse_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    content = await file.read()
    return WarehouseFileService(db).upload_unbound_file(
        file_name=file.filename or "warehouse-file.xlsx",
        content=content,
        current_user=current_user,
    )


@router.get("/{receipt_id}/boxes", response_model=list[BoxOut])
def list_receipt_boxes(
    receipt_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    return WarehouseFileService(db).list_receipt_boxes(receipt_id)


@router.post("/{receipt_id}/bind-waybill", response_model=WarehouseReceiptListOut)
def bind_receipt_to_waybill(
    receipt_id: int,
    payload: WarehouseReceiptBindRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    service = WarehouseFileService(db)
    service.bind_receipt_to_waybill(receipt_id, payload.target_waybill_id, current_user)
    return service.get_receipt_summary(receipt_id)


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unbound_receipt(
    receipt_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    WarehouseFileService(db).delete_unbound_receipt(receipt_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
