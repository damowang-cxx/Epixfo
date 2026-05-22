from datetime import datetime, timedelta, timezone

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import not_found
from app.models import User, UserDailyOnlineStats, UserLoginLog, UserPresenceLog
from app.models.enums import UserRoleCode
from app.services.permission_service import PermissionService
from app.utils.datetime_utils import local_now, utc_now

ONLINE_THRESHOLD = timedelta(minutes=2)
DEFAULT_SESSION_DAYS = 30
MAX_SESSION_DAYS = 365

ROLE_RANKS = {
    UserRoleCode.ADMIN.value: 1,
    UserRoleCode.ROUTE_STAFF.value: 2,
    UserRoleCode.CUSTOMER_SERVICE.value: 3,
    UserRoleCode.CUSTOMS_STAFF.value: 4,
}
DEFAULT_ROLE_RANK = 99


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _duration_seconds(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds()))


class PresenceService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def role_rank(user: User) -> int:
        return min((ROLE_RANKS.get(code, DEFAULT_ROLE_RANK) for code in PermissionService.role_codes(user)), default=DEFAULT_ROLE_RANK)

    @staticmethod
    def primary_role(user: User) -> UserRoleCode | None:
        role_codes = sorted(PermissionService.role_codes(user), key=lambda code: ROLE_RANKS.get(code, DEFAULT_ROLE_RANK))
        if not role_codes:
            return None
        try:
            return UserRoleCode(role_codes[0])
        except ValueError:
            return None

    @staticmethod
    def is_online(user: User, now: datetime | None = None) -> bool:
        current = _aware_utc(now or utc_now())
        last_seen = _aware_utc(user.last_seen_at)
        return bool(user.is_active and last_seen and current and last_seen >= current - ONLINE_THRESHOLD)

    def heartbeat(self, user: User, ip_address: str | None, user_agent: str | None) -> User:
        now = utc_now()
        previous_seen = user.last_seen_at
        user.last_seen_at = now
        self.db.add(UserPresenceLog(user_id=user.id, heartbeat_at=now, ip_address=ip_address, user_agent=user_agent))
        previous_seen_utc = _aware_utc(previous_seen)
        if previous_seen_utc and now - previous_seen_utc <= ONLINE_THRESHOLD:
            stat_date = local_now().date()
            stat = self.db.scalar(
                select(UserDailyOnlineStats).where(
                    UserDailyOnlineStats.user_id == user.id,
                    UserDailyOnlineStats.stat_date == stat_date,
                )
            )
            if stat is None:
                stat = UserDailyOnlineStats(user_id=user.id, stat_date=stat_date, total_online_seconds=0)
                self.db.add(stat)
            stat.total_online_seconds += int((now - previous_seen_utc).total_seconds())
        self.db.commit()
        self.db.refresh(user)
        return user

    def online_users(self) -> list[User]:
        cutoff = utc_now() - ONLINE_THRESHOLD
        return list(self.db.scalars(select(User).where(User.last_seen_at >= cutoff, User.is_active.is_(True))))

    def user_statuses(self) -> list[dict]:
        now = utc_now()
        users = list(self.db.scalars(select(User).options(selectinload(User.roles))))
        statuses = [self._user_status(user, now) for user in users]
        statuses.sort(
            key=lambda item: (
                0 if item["online"] else 1,
                item["role_rank"],
                item["username"].lower(),
                item["id"],
            )
        )
        return statuses

    def user_sessions(self, user_id: int, days: int = DEFAULT_SESSION_DAYS) -> list[dict]:
        days = max(1, min(days, MAX_SESSION_DAYS))
        now = utc_now()
        user = self.db.scalar(select(User).options(selectinload(User.roles)).where(User.id == user_id))
        if user is None:
            raise not_found("User not found")

        since = now - timedelta(days=days)
        logs = list(
            self.db.scalars(
                select(UserLoginLog)
                .where(UserLoginLog.user_id == user_id, UserLoginLog.login_at >= since)
                .order_by(UserLoginLog.login_at.desc(), UserLoginLog.id.desc())
            )
        )
        latest_open_id = next((item.id for item in logs if item.logout_at is None), None)
        online = self.is_online(user, now)
        return [self._session_status(item, user, now, online, latest_open_id) for item in logs]

    def daily_stats(self, user_id: int) -> list[UserDailyOnlineStats]:
        return list(
            self.db.scalars(
                select(UserDailyOnlineStats)
                .where(UserDailyOnlineStats.user_id == user_id)
                .order_by(UserDailyOnlineStats.stat_date.desc())
            )
        )

    def _user_status(self, user: User, now: datetime) -> dict:
        online = self.is_online(user, now)
        last_seen = _aware_utc(user.last_seen_at)
        now_utc = _aware_utc(now)
        if not user.is_active:
            status = "disabled"
        elif online:
            status = "online"
        else:
            status = "offline"
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "roles": user.roles,
            "last_login_at": user.last_login_at,
            "last_seen_at": user.last_seen_at,
            "last_seen_age_seconds": _duration_seconds(last_seen, now_utc) if last_seen and now_utc else None,
            "online": online,
            "status": status,
            "primary_role": self.primary_role(user),
            "role_rank": self.role_rank(user),
        }

    def _session_status(
        self,
        log: UserLoginLog,
        user: User,
        now: datetime,
        user_online: bool,
        latest_open_id: int | None,
    ) -> dict:
        login_at = _aware_utc(log.login_at) or now
        logout_at = _aware_utc(log.logout_at)
        effective_logout_at: datetime | None
        if logout_at is not None:
            status = "logged_out"
            effective_logout_at = logout_at
            duration_end = logout_at
        elif user_online and log.id == latest_open_id:
            status = "online"
            effective_logout_at = None
            duration_end = now
        else:
            status = "timeout"
            last_seen = _aware_utc(user.last_seen_at)
            effective_logout_at = last_seen if last_seen and last_seen >= login_at else login_at
            duration_end = effective_logout_at
        return {
            "id": log.id,
            "login_at": log.login_at,
            "logout_at": log.logout_at,
            "effective_logout_at": effective_logout_at,
            "duration_seconds": _duration_seconds(login_at, duration_end),
            "status": status,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
        }
