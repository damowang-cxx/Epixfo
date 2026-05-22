from datetime import timedelta

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import Select

from app.core.exceptions import forbidden
from app.models import AirWaybill, User, WaybillPlan
from app.models.enums import UserRoleCode, WaybillLifecycleStatus
from app.utils.datetime_utils import local_now


VISIBLE_TO_CUSTOMER_SERVICE = {
    WaybillLifecycleStatus.WAREHOUSE_RECEIVED,
    WaybillLifecycleStatus.LOADED,
    WaybillLifecycleStatus.DEPARTED,
    WaybillLifecycleStatus.ARRIVED,
    WaybillLifecycleStatus.PICKUP_NOTIFIED,
    WaybillLifecycleStatus.PICKED_UP,
}

SENSITIVE_WAYBILL_FIELDS = {
    "quotation",
    "air_freight_cost",
    "payment_date",
    "data_charge",
    "internal_remark",
}


class PermissionService:
    @staticmethod
    def role_codes(user: User) -> set[str]:
        if user.is_superuser:
            return {UserRoleCode.ADMIN.value}
        return {role.code.value if hasattr(role.code, "value") else str(role.code) for role in user.roles}

    @classmethod
    def has_role(cls, user: User, role: UserRoleCode) -> bool:
        return role.value in cls.role_codes(user)

    @classmethod
    def require_any(cls, user: User, roles: set[UserRoleCode]) -> None:
        user_roles = cls.role_codes(user)
        if not user_roles.intersection({role.value for role in roles}):
            raise forbidden()

    @classmethod
    def can_write_waybills(cls, user: User) -> bool:
        return bool(cls.role_codes(user).intersection({UserRoleCode.ADMIN.value, UserRoleCode.ROUTE_STAFF.value}))

    @classmethod
    def can_manage_alerts(cls, user: User) -> bool:
        return cls.has_role(user, UserRoleCode.ADMIN)

    @classmethod
    def can_manage_users(cls, user: User) -> bool:
        return cls.has_role(user, UserRoleCode.ADMIN) or cls.has_role(user, UserRoleCode.ROUTE_STAFF)

    @classmethod
    def assert_waybill_write(cls, user: User) -> None:
        if not cls.can_write_waybills(user):
            raise forbidden("Only admins and route staff can modify waybills")

    @classmethod
    def filter_waybill_query(cls, query: Select[tuple[AirWaybill]], user: User) -> Select[tuple[AirWaybill]]:
        roles = cls.role_codes(user)
        if UserRoleCode.ADMIN.value in roles or UserRoleCode.ROUTE_STAFF.value in roles:
            return query
        if UserRoleCode.CUSTOMER_SERVICE.value in roles:
            return query.where(AirWaybill.lifecycle_status.in_(VISIBLE_TO_CUSTOMER_SERVICE))
        if UserRoleCode.CUSTOMS_STAFF.value in roles:
            today = local_now().date()
            return query.join(WaybillPlan).where(
                WaybillPlan.planned_flight_date >= today,
                WaybillPlan.planned_flight_date <= today + timedelta(days=3),
            )
        return query.where(False)

    @classmethod
    def redact_waybill(cls, data: dict, user: User) -> dict:
        if cls.has_role(user, UserRoleCode.CUSTOMER_SERVICE) and not cls.has_role(user, UserRoleCode.ADMIN):
            for field in SENSITIVE_WAYBILL_FIELDS:
                data[field] = None
        return data
