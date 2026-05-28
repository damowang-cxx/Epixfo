from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.box import BoxCreate, BoxOut, BoxUpdate, BoxVolumeRecalculationRequest, BoxVolumeRecalculationResult, WarehouseFileUploadResult, WarehouseReceiptBindPrebookingRequest, WarehouseReceiptListOut
from app.schemas.common import PageResponse
from app.schemas.prebooking import WaybillPrebookingConvert, WaybillPrebookingCreate, WaybillPrebookingOut, WaybillPrebookingUpdate
from app.schemas.waybill import WaybillOut
from app.services.prebooking_service import PrebookingService
from app.services.warehouse_file_service import WarehouseFileService

router = APIRouter(prefix="/prebookings", tags=["prebookings"])


@router.get("", response_model=PageResponse[WaybillPrebookingOut])
def list_prebookings(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total, page, page_size = PrebookingService(db).list(
        current_user,
        page=page,
        page_size=page_size,
        status=status,
    )
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=WaybillPrebookingOut)
def create_prebooking(
    payload: WaybillPrebookingCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).create(payload, current_user)
    return PrebookingService(db).to_out(prebooking)


@router.get("/{prebooking_id}", response_model=WaybillPrebookingOut)
def get_prebooking(prebooking_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    return PrebookingService(db).to_out(prebooking)


@router.patch("/{prebooking_id}", response_model=WaybillPrebookingOut)
def update_prebooking(
    prebooking_id: int,
    payload: WaybillPrebookingUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).update(prebooking_id, payload, current_user)
    return PrebookingService(db).to_out(prebooking)


@router.delete("/{prebooking_id}", status_code=204)
def delete_prebooking(prebooking_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PrebookingService(db).delete(prebooking_id, current_user)
    return Response(status_code=204)


@router.post("/{prebooking_id}/convert", response_model=WaybillOut)
def convert_prebooking(
    prebooking_id: int,
    payload: WaybillPrebookingConvert,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PrebookingService(db).convert(prebooking_id, payload, current_user)


@router.get("/{prebooking_id}/boxes", response_model=list[BoxOut])
def prebooking_boxes(prebooking_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    return WarehouseFileService(db).list_prebooking_boxes(prebooking.id)


@router.post("/{prebooking_id}/boxes", response_model=BoxOut)
def create_prebooking_box(
    prebooking_id: int,
    payload: BoxCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    return WarehouseFileService(db).create_prebooking_box(prebooking, payload, current_user)


@router.patch("/{prebooking_id}/boxes/{box_id}", response_model=BoxOut)
def update_prebooking_box(
    prebooking_id: int,
    box_id: int,
    payload: BoxUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    return WarehouseFileService(db).update_prebooking_box(
        prebooking,
        box_id,
        current_user,
        box_no=payload.box_no,
        is_general_cargo=payload.is_general_cargo,
    )


@router.delete("/{prebooking_id}/boxes/{box_id}", status_code=204)
def delete_prebooking_box(
    prebooking_id: int,
    box_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    WarehouseFileService(db).delete_prebooking_box(prebooking, box_id, current_user)
    return Response(status_code=204)


@router.post("/{prebooking_id}/boxes/recalculate-volume", response_model=BoxVolumeRecalculationResult)
def recalculate_prebooking_box_volumes(
    prebooking_id: int,
    payload: BoxVolumeRecalculationRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    return WarehouseFileService(db).recalculate_prebooking_box_volumes(
        prebooking,
        payload.target_volume,
        current_user,
        warehouse_receipt_id=payload.warehouse_receipt_id,
    )


@router.post("/{prebooking_id}/warehouse-file", response_model=WarehouseFileUploadResult)
async def upload_prebooking_warehouse_file(
    prebooking_id: int,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    content = await file.read()
    return WarehouseFileService(db).upload_for_prebooking(
        prebooking,
        file.filename or "warehouse-file.xlsx",
        content,
        current_user,
    )


@router.post("/{prebooking_id}/receipts", response_model=WarehouseReceiptListOut)
def bind_receipt_to_prebooking(
    prebooking_id: int,
    payload: WarehouseReceiptBindPrebookingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prebooking = PrebookingService(db).get(prebooking_id, current_user)
    service = WarehouseFileService(db)
    receipt = service.bind_receipt_to_prebooking(payload.receipt_id, prebooking, current_user)
    return service.get_receipt_summary(receipt.id)
