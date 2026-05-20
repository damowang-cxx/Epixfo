from datetime import timedelta

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserDailyOnlineStats, UserPresenceLog
from app.utils.datetime_utils import local_now, utc_now


class PresenceService:
    def __init__(self, db: Session):
        self.db = db

    def heartbeat(self, user: User, ip_address: str | None, user_agent: str | None) -> User:
        now = utc_now()
        previous_seen = user.last_seen_at
        user.last_seen_at = now
        self.db.add(UserPresenceLog(user_id=user.id, heartbeat_at=now, ip_address=ip_address, user_agent=user_agent))
        if previous_seen and now - previous_seen <= timedelta(minutes=3):
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
            stat.total_online_seconds += int((now - previous_seen).total_seconds())
        self.db.commit()
        self.db.refresh(user)
        return user

    def online_users(self) -> list[User]:
        cutoff = utc_now() - timedelta(minutes=3)
        return list(self.db.scalars(select(User).where(User.last_seen_at >= cutoff, User.is_active.is_(True))))

    def daily_stats(self, user_id: int) -> list[UserDailyOnlineStats]:
        return list(
            self.db.scalars(
                select(UserDailyOnlineStats)
                .where(UserDailyOnlineStats.user_id == user_id)
                .order_by(UserDailyOnlineStats.stat_date.desc())
            )
        )
