from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserTablePreference


class UserPreferenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_table_preference(self, user_id: int, table_key: str) -> UserTablePreference | None:
        return self.db.scalar(
            select(UserTablePreference).where(
                UserTablePreference.user_id == user_id,
                UserTablePreference.table_key == table_key,
            )
        )

    def upsert_table_preference(
        self,
        user_id: int,
        table_key: str,
        column_order: list[str],
    ) -> UserTablePreference:
        preference = self.get_table_preference(user_id, table_key)
        if preference is None:
            preference = UserTablePreference(
                user_id=user_id,
                table_key=table_key,
                column_order=column_order,
            )
            self.db.add(preference)
        else:
            preference.column_order = column_order
        self.db.flush()
        return preference
