from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import UserRoleCode
from app.schemas.monitor import AutoFlightQuerySettingsOut, AutoFlightQuerySettingsUpdate
from app.services.auto_flight_query_settings_service import AutoFlightQuerySettingsService
from app.services.monitor_service import MonitorService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/settings", response_model=AutoFlightQuerySettingsOut)
def get_monitor_settings(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return AutoFlightQuerySettingsService(db).get()


@router.patch("/settings", response_model=AutoFlightQuerySettingsOut)
def update_monitor_settings(
    payload: AutoFlightQuerySettingsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return AutoFlightQuerySettingsService(db).update(payload)


@router.post("/due-waybills/run")
async def run_due_waybills(
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    processed = await MonitorService(db).run_due_waybills(limit=limit)
    return {"processed": processed}
