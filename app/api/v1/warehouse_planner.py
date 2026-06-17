from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.warehouse_planner import (
    WarehousePlannerBulkImportResult,
    WarehousePlannerCandidatesOut,
    WarehousePlannerCommitRequest,
    WarehousePlannerCommitResult,
    WarehousePlannerDraftOut,
    WarehousePlannerDraftSave,
    WarehousePlannerRowsRequest,
    WarehousePlannerValidateResult,
)
from app.services.warehouse_planner_service import WarehousePlannerService

router = APIRouter(prefix="/warehouse-planner", tags=["warehouse-planner"])


@router.get("/draft", response_model=WarehousePlannerDraftOut)
def get_planning_draft(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return WarehousePlannerService(db).get_draft(current_user)


@router.put("/draft", response_model=WarehousePlannerDraftOut)
def save_planning_draft(
    payload: WarehousePlannerDraftSave,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return WarehousePlannerService(db).save_draft(payload, current_user)


@router.delete("/draft", status_code=204)
def clear_planning_draft(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    WarehousePlannerService(db).clear_draft(current_user)
    return Response(status_code=204)


@router.get("/candidates", response_model=WarehousePlannerCandidatesOut)
def planning_candidates(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return WarehousePlannerService(db).candidates(current_user)


@router.post("/bulk-import", response_model=WarehousePlannerBulkImportResult)
async def bulk_import_planning_rows(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return WarehousePlannerService(db).bulk_import(file.filename or "waybill-import.xlsx", content, current_user)


@router.post("/validate", response_model=WarehousePlannerValidateResult)
def validate_planning_rows(
    payload: WarehousePlannerRowsRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return WarehousePlannerService(db).validate_rows(payload, current_user)


@router.post("/commit", response_model=WarehousePlannerCommitResult)
def commit_planning_rows(
    payload: WarehousePlannerCommitRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return WarehousePlannerService(db).commit(payload, current_user)


@router.get("/draft/export")
def export_planning_draft(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    content = WarehousePlannerService(db).export_draft(current_user)
    filename = "排仓编辑区.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
