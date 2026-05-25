from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRoleCode, WaybillLifecycleStatus
from app.schemas.user import RoleOut


class HeartbeatResponse(BaseModel):
    user_id: int
    last_seen_at: datetime
    online: bool = True


class OnlineUserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    last_seen_at: datetime | None = None


class DailyOnlineStatOut(BaseModel):
    user_id: int
    stat_date: date
    total_online_seconds: int


class PresenceUserStatusOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    is_active: bool
    roles: list[RoleOut] = []
    last_login_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_seen_age_seconds: int | None = None
    online: bool
    status: str
    primary_role: UserRoleCode | None = None
    role_rank: int


class PresenceUserSessionOut(BaseModel):
    id: int
    login_at: datetime
    logout_at: datetime | None = None
    effective_logout_at: datetime | None = None
    duration_seconds: int
    status: str
    ip_address: str | None = None
    user_agent: str | None = None


class PresenceWaybillViewLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    waybill_id: int | None = None
    waybill_no: str
    lifecycle_status: WaybillLifecycleStatus | None = None
    viewed_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
