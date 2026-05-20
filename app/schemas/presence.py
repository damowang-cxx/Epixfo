from datetime import date, datetime

from pydantic import BaseModel


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
