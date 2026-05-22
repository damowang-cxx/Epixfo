from datetime import date, datetime

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import AlertLevel, UserRoleCode, WaybillLifecycleStatus
from app.repositories.waybill_repository import WaybillRepository
from app.schemas.alert import AlertOut
from app.schemas.box import BoxOut, WarehouseFileUploadResult
from app.schemas.common import PageResponse
from app.schemas.lookup import WaybillLookupRequest, WaybillLookupResponse
from app.schemas.waybill import (
    ManualStatusRequest,
    WaybillAssemblyEventOut,
    WaybillCreate,
    WaybillOfficialFlightSegmentOut,
    WaybillOfficialInfoOut,
    WaybillOut,
    WaybillQuerySnapshotOut,
    WaybillStatusCount,
    WaybillStatusEventOut,
    WaybillUpdate,
)
from app.services.lookup_service import WaybillLookupService
from app.services.permission_service import PermissionService
from app.services.warehouse_file_service import WarehouseFileService
from app.services.waybill_service import WaybillService

router = APIRouter(prefix="/waybills", tags=["waybills"])


def _waybill_response(waybill, current_user):
    data = WaybillOut.model_validate(waybill).model_dump()
    return PermissionService.redact_waybill(data, current_user)


@router.get("", response_model=PageResponse[WaybillOut])
def list_waybills(
    waybill_no: str | None = None,
    carrier_code: str | None = None,
    destination_port: str | None = None,
    planned_flight_no: str | None = None,
    planned_flight_date_from: date | None = None,
    planned_flight_date_to: date | None = None,
    lifecycle_status: WaybillLifecycleStatus | None = None,
    alert_level: AlertLevel | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total, page, page_size = WaybillService(db).list(
        current_user,
        page=page,
        page_size=page_size,
        waybill_no=waybill_no,
        carrier_code=carrier_code,
        destination_port=destination_port,
        planned_flight_no=planned_flight_no,
        planned_flight_date_from=planned_flight_date_from,
        planned_flight_date_to=planned_flight_date_to,
        lifecycle_status=lifecycle_status,
        alert_level=alert_level,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    return PageResponse(items=[_waybill_response(item, current_user) for item in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=WaybillOut)
def create_waybill(payload: WaybillCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    waybill = WaybillService(db).create(payload, current_user)
    return _waybill_response(waybill, current_user)


@router.get("/status-counts", response_model=list[WaybillStatusCount])
def status_counts(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return WaybillService(db).status_counts(current_user)


@router.post("/lookup", response_model=WaybillLookupResponse)
async def lookup_waybill(
    payload: WaybillLookupRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN, UserRoleCode.ROUTE_STAFF})
    return await WaybillLookupService(db).lookup(payload.waybill_no, adapter_code=payload.adapter_code)


@router.get("/{waybill_id}", response_model=WaybillOut)
def get_waybill(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    waybill = WaybillService(db).get_visible(waybill_id, current_user)
    return _waybill_response(waybill, current_user)


@router.patch("/{waybill_id}", response_model=WaybillOut)
def update_waybill(
    waybill_id: int,
    payload: WaybillUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    waybill = WaybillService(db).update(waybill_id, payload, current_user)
    return _waybill_response(waybill, current_user)


@router.get("/{waybill_id}/boxes", response_model=list[BoxOut])
def waybill_boxes(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WarehouseFileService(db).list_boxes(waybill_id)


@router.post("/{waybill_id}/warehouse-file", response_model=WarehouseFileUploadResult)
async def upload_warehouse_file(
    waybill_id: int,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return WarehouseFileService(db).upload_for_waybill(
        waybill_id=waybill_id,
        file_name=file.filename or "warehouse-file.xlsx",
        content=content,
        current_user=current_user,
    )


@router.post("/{waybill_id}/void", response_model=WaybillOut)
def void_waybill(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    waybill = WaybillService(db).void(waybill_id, current_user)
    return _waybill_response(waybill, current_user)


@router.post("/{waybill_id}/manual-status", response_model=WaybillOut)
def manual_status(
    waybill_id: int,
    payload: ManualStatusRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    waybill = WaybillService(db).manual_status(waybill_id, payload, current_user)
    return _waybill_response(waybill, current_user)


@router.post("/{waybill_id}/trigger-query", response_model=WaybillQuerySnapshotOut)
async def trigger_query(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return await WaybillService(db).trigger_query(waybill_id, current_user)


@router.get("/{waybill_id}/official-info", response_model=WaybillOfficialInfoOut | None)
def official_info(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).official_info(waybill_id)


@router.get("/{waybill_id}/official-flight-segments", response_model=list[WaybillOfficialFlightSegmentOut])
def official_segments(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).official_segments(waybill_id)


@router.get("/{waybill_id}/status-events", response_model=list[WaybillStatusEventOut])
def status_events(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).status_events(waybill_id)


@router.get("/{waybill_id}/assembly-events", response_model=list[WaybillAssemblyEventOut])
def assembly_events(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).assembly_events(waybill_id)


@router.get("/{waybill_id}/query-snapshots", response_model=list[WaybillQuerySnapshotOut])
def query_snapshots(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).query_snapshots(waybill_id)


@router.get("/{waybill_id}/alerts", response_model=list[AlertOut])
def waybill_alerts(waybill_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WaybillService(db).get_visible(waybill_id, current_user)
    return WaybillRepository(db).alerts(waybill_id)
