from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        user_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        before_data: dict | None = None,
        after_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                before_data=before_data,
                after_data=after_data,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

    def list(self, skip: int = 0, limit: int = 100) -> list[AuditLog]:
        return list(self.db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(skip).limit(limit)))
