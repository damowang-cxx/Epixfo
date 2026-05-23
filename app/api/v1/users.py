from fastapi import APIRouter, Depends, Response

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import not_found
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.models.enums import UserRoleCode
from app.services.permission_service import PermissionService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService(db).list_users(current_user)


@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService(db).create_user(payload, current_user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != user_id:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
    user = UserRepository(db).get(user_id)
    if user is None:
        raise not_found("User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService(db).update_user(user_id, payload, current_user)


@router.post("/{user_id}/disable", response_model=UserOut)
def disable_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService(db).set_active(user_id, False, current_user)


@router.post("/{user_id}/enable", response_model=UserOut)
def enable_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService(db).set_active(user_id, True, current_user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    UserService(db).delete_user(user_id, current_user)
    return Response(status_code=204)
