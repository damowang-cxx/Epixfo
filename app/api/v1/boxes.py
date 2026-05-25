from fastapi import APIRouter, Depends, File, UploadFile

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.box import (
    BoxBatchBindRequest,
    BoxBatchOperationResult,
    BoxBatchTransferRequest,
    BoxBatchUnbindRequest,
    BoxOut,
    WarehouseFileUploadResult,
)
from app.schemas.common import PageResponse
from app.services.permission_service import PermissionService
from app.services.warehouse_file_service import WarehouseFileService

router = APIRouter(prefix="/boxes", tags=["boxes"])


@router.get("/unbound", response_model=PageResponse[BoxOut])
def list_unbound_boxes(
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    items, total, page, page_size = WarehouseFileService(db).list_unbound_boxes(page=page, page_size=page_size)
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


@router.post("/batch-bind", response_model=BoxBatchOperationResult)
def batch_bind_boxes(
    payload: BoxBatchBindRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    return WarehouseFileService(db).batch_bind_boxes(payload.box_ids, payload.target_waybill_id, current_user)


@router.post("/batch-transfer", response_model=BoxBatchOperationResult)
def batch_transfer_boxes(
    payload: BoxBatchTransferRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    return WarehouseFileService(db).batch_transfer_boxes(
        payload.box_ids,
        payload.target_type,
        current_user,
        target_waybill_id=payload.target_waybill_id,
        unbound_reason=payload.unbound_reason,
        unbound_remark=payload.unbound_remark,
    )


@router.post("/batch-unbind", response_model=BoxBatchOperationResult)
def batch_unbind_boxes(
    payload: BoxBatchUnbindRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.assert_waybill_write(current_user)
    return WarehouseFileService(db).batch_unbind_boxes(payload.box_ids, current_user)
