from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.models import User
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.schemas.user_preference import TableColumnPreferenceIn, TableColumnPreferenceOut


class UserPreferenceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserPreferenceRepository(db)

    def get_table_columns(self, current_user: User, table_key: str) -> TableColumnPreferenceOut:
        self._validate_table_key(table_key)
        preference = self.repo.get_table_preference(current_user.id, table_key)
        return TableColumnPreferenceOut(
            table_key=table_key,
            column_order=list(preference.column_order) if preference is not None else [],
        )

    def set_table_columns(
        self,
        current_user: User,
        table_key: str,
        payload: TableColumnPreferenceIn,
    ) -> TableColumnPreferenceOut:
        self._validate_table_key(table_key)
        column_order = [column for column in payload.column_order if column]
        preference = self.repo.upsert_table_preference(current_user.id, table_key, column_order)
        self.db.commit()
        return TableColumnPreferenceOut(table_key=preference.table_key, column_order=list(preference.column_order))

    @staticmethod
    def _validate_table_key(table_key: str) -> None:
        if not table_key or len(table_key) > 128:
            raise bad_request("invalid_table_key")
