from fastapi import APIRouter, Depends, Query, Request

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user, user_agent
from app.core.database import get_db
from app.models.enums import UserRoleCode
from app.schemas.presence import (
    DailyOnlineStatOut,
    HeartbeatResponse,
    OnlineUserOut,
    PresenceUserSessionOut,
    PresenceUserStatusOut,
)
from app.services.permission_service import PermissionService
from app.services.presence_service import DEFAULT_SESSION_DAYS, PresenceService

router = APIRouter(prefix="/presence", tags=["presence"])


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    user = PresenceService(db).heartbeat(current_user, client_ip(request), user_agent(request))
    return HeartbeatResponse(user_id=user.id, last_seen_at=user.last_seen_at)


@router.get("/online-users", response_model=list[OnlineUserOut])
def online_users(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return PresenceService(db).online_users()


@router.get("/users", response_model=list[PresenceUserStatusOut])
def users(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return PresenceService(db).user_statuses()


@router.get("/users/{user_id}/sessions", response_model=list[PresenceUserSessionOut])
def user_sessions(
    user_id: int,
    days: int = Query(DEFAULT_SESSION_DAYS, ge=1, le=365),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return PresenceService(db).user_sessions(user_id, days)


@router.get("/users/{user_id}/daily-stats", response_model=list[DailyOnlineStatOut])
def daily_stats(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    return PresenceService(db).daily_stats(user_id)
