from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import not_found
from app.models.enums import AlertStatus, UserRoleCode
from app.schemas.alert import AlertOut
from app.services.alert_service import AlertService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: AlertStatus | None = None,
    alert_type: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return AlertService(db).list_visible(current_user, status=status, alert_type=alert_type)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    alert = AlertService(db).transition(alert_id, AlertStatus.ACKNOWLEDGED, current_user)
    if alert is None:
        raise not_found("Alert not found")
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    alert = AlertService(db).transition(alert_id, AlertStatus.RESOLVED, current_user)
    if alert is None:
        raise not_found("Alert not found")
    return alert


@router.post("/{alert_id}/ignore", response_model=AlertOut)
def ignore(alert_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    alert = AlertService(db).transition(alert_id, AlertStatus.IGNORED, current_user)
    if alert is None:
        raise not_found("Alert not found")
    return alert
