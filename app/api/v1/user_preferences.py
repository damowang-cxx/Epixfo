from fastapi import APIRouter, Depends

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.user_preference import TableColumnPreferenceIn, TableColumnPreferenceOut
from app.services.user_preference_service import UserPreferenceService

router = APIRouter(prefix="/user-preferences", tags=["user-preferences"])


@router.get("/table-columns/{table_key}", response_model=TableColumnPreferenceOut)
def get_table_columns(
    table_key: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserPreferenceService(db).get_table_columns(current_user, table_key)


@router.put("/table-columns/{table_key}", response_model=TableColumnPreferenceOut)
def set_table_columns(
    table_key: str,
    payload: TableColumnPreferenceIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserPreferenceService(db).set_table_columns(current_user, table_key, payload)
