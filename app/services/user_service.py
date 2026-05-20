from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRoleCode
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.permission_service import PermissionService


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def list_users(self, current_user: User, skip: int = 0, limit: int = 100) -> list[User]:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
        return self.repo.list(skip, limit)

    def create_user(self, payload: UserCreate, current_user: User | None = None) -> User:
        if current_user is not None:
            if not PermissionService.can_manage_users(current_user):
                raise forbidden()
            if PermissionService.has_role(current_user, UserRoleCode.ROUTE_STAFF) and not PermissionService.has_role(
                current_user, UserRoleCode.ADMIN
            ):
                allowed = {UserRoleCode.CUSTOMER_SERVICE, UserRoleCode.CUSTOMS_STAFF}
                if not set(payload.role_codes).issubset(allowed):
                    raise forbidden("Route staff can only create customer service or customs staff users")
        if self.repo.get_by_username(payload.username):
            raise bad_request("Username already exists")
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            email=payload.email,
            phone=payload.phone,
            created_by=current_user.id if current_user else None,
        )
        self.db.add(user)
        self.db.flush()
        self.repo.set_roles(user, payload.role_codes)
        self.db.commit()
        return self.repo.get(user.id) or user

    def update_user(self, user_id: int, payload: UserUpdate, current_user: User) -> User:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
        user = self.repo.get(user_id)
        if user is None:
            raise not_found("User not found")
        for field in ["username", "display_name", "email", "phone", "is_active"]:
            value = getattr(payload, field, None)
            if value is not None:
                setattr(user, field, value)
        if payload.password:
            user.password_hash = hash_password(payload.password)
        if payload.role_codes is not None:
            self.repo.set_roles(user, payload.role_codes)
        self.db.commit()
        return self.repo.get(user.id) or user

    def set_active(self, user_id: int, is_active: bool, current_user: User) -> User:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
        user = self.repo.get(user_id)
        if user is None:
            raise not_found("User not found")
        user.is_active = is_active
        self.db.commit()
        return self.repo.get(user.id) or user
