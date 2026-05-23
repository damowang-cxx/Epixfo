from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.core.security import hash_password
import app.models.all  # noqa: F401
from app.models import (
    AirWaybill,
    AuditLog,
    BoxDocument,
    User,
    UserDailyOnlineStats,
    UserLoginLog,
    UserPresenceLog,
    UserRefreshToken,
    UserRole,
    WarehouseReceipt,
    WaybillAlert,
    WaybillBoard,
)
from app.models.enums import UserRoleCode
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.permission_service import PermissionService


class UserService:
    ROUTE_STAFF_VISIBLE_ROLES = {
        UserRoleCode.ROUTE_STAFF.value,
        UserRoleCode.CUSTOMER_SERVICE.value,
        UserRoleCode.CUSTOMS_STAFF.value,
    }
    ROUTE_STAFF_MANAGED_ROLES = {
        UserRoleCode.CUSTOMER_SERVICE,
        UserRoleCode.CUSTOMS_STAFF,
    }

    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def list_users(self, current_user: User, skip: int = 0, limit: int = 100) -> list[User]:
        if PermissionService.has_role(current_user, UserRoleCode.ADMIN):
            return self.repo.list(skip, limit)
        PermissionService.require_any(current_user, {UserRoleCode.ROUTE_STAFF})
        return [
            user
            for user in self.repo.list(skip, limit)
            if not self._is_admin_user(user)
            and bool(PermissionService.role_codes(user).intersection(self.ROUTE_STAFF_VISIBLE_ROLES))
        ]

    def create_user(self, payload: UserCreate, current_user: User | None = None) -> User:
        if current_user is not None:
            if not PermissionService.can_manage_users(current_user):
                raise forbidden()
            if PermissionService.has_role(current_user, UserRoleCode.ROUTE_STAFF) and not PermissionService.has_role(
                current_user, UserRoleCode.ADMIN
            ):
                allowed = {UserRoleCode.CUSTOMER_SERVICE, UserRoleCode.CUSTOMS_STAFF}
                if not payload.role_codes or not set(payload.role_codes).issubset(allowed):
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
        user = self.repo.get(user_id)
        if user is None:
            raise not_found("User not found")
        self._assert_can_manage_target_user(current_user, user, payload.role_codes)
        if payload.username and payload.username != user.username:
            existing = self.repo.get_by_username(payload.username)
            if existing is not None and existing.id != user.id:
                raise bad_request("Username already exists")
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
        user = self.repo.get(user_id)
        if user is None:
            raise not_found("User not found")
        self._assert_can_manage_target_user(current_user, user, None)
        user.is_active = is_active
        self.db.commit()
        return self.repo.get(user.id) or user

    def delete_user(self, user_id: int, current_user: User) -> None:
        user = self.repo.get(user_id)
        if user is None:
            raise not_found("User not found")
        if user.id == current_user.id:
            raise bad_request("cannot_delete_self")
        self._assert_can_manage_target_user(current_user, user, None)

        self._detach_business_references(user.id)
        self._delete_user_owned_records(user.id)
        self.db.delete(user)
        self.db.commit()

    def _assert_can_manage_target_user(
        self,
        current_user: User,
        target_user: User,
        next_role_codes: list[UserRoleCode] | None,
    ) -> None:
        if PermissionService.has_role(current_user, UserRoleCode.ADMIN):
            return
        PermissionService.require_any(current_user, {UserRoleCode.ROUTE_STAFF})
        if not self._is_route_staff_manageable_user(target_user):
            raise forbidden("Route staff can only manage customer service or customs staff users")
        if next_role_codes is not None:
            if not next_role_codes or not set(next_role_codes).issubset(self.ROUTE_STAFF_MANAGED_ROLES):
                raise forbidden("Route staff can only assign customer service or customs staff roles")

    @classmethod
    def _is_admin_user(cls, user: User) -> bool:
        return user.is_superuser or PermissionService.has_role(user, UserRoleCode.ADMIN)

    @classmethod
    def _is_route_staff_manageable_user(cls, user: User) -> bool:
        roles = PermissionService.role_codes(user)
        return bool(roles) and roles.issubset({role.value for role in cls.ROUTE_STAFF_MANAGED_ROLES})

    def _detach_business_references(self, user_id: int) -> None:
        self.db.execute(update(User).where(User.created_by == user_id).values(created_by=None))
        self.db.execute(
            update(AirWaybill).where(AirWaybill.document_operator_id == user_id).values(document_operator_id=None)
        )
        self.db.execute(update(AirWaybill).where(AirWaybill.route_staff_id == user_id).values(route_staff_id=None))
        self.db.execute(update(AirWaybill).where(AirWaybill.created_by == user_id).values(created_by=None))
        self.db.execute(update(AirWaybill).where(AirWaybill.updated_by == user_id).values(updated_by=None))
        self.db.execute(update(WaybillBoard).where(WaybillBoard.created_by == user_id).values(created_by=None))
        self.db.execute(update(WaybillBoard).where(WaybillBoard.updated_by == user_id).values(updated_by=None))
        self.db.execute(update(BoxDocument).where(BoxDocument.uploaded_by == user_id).values(uploaded_by=None))
        self.db.execute(update(WarehouseReceipt).where(WarehouseReceipt.uploaded_by == user_id).values(uploaded_by=None))
        self.db.execute(update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None))
        self.db.execute(update(WaybillAlert).where(WaybillAlert.acknowledged_by == user_id).values(acknowledged_by=None))
        self.db.execute(update(WaybillAlert).where(WaybillAlert.resolved_by == user_id).values(resolved_by=None))

    def _delete_user_owned_records(self, user_id: int) -> None:
        self.db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        self.db.execute(delete(UserRefreshToken).where(UserRefreshToken.user_id == user_id))
        self.db.execute(delete(UserLoginLog).where(UserLoginLog.user_id == user_id))
        self.db.execute(delete(UserPresenceLog).where(UserPresenceLog.user_id == user_id))
        self.db.execute(delete(UserDailyOnlineStats).where(UserDailyOnlineStats.user_id == user_id))
