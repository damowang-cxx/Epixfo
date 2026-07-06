from types import SimpleNamespace

from app.models.enums import UserRoleCode
from app.services.permission_service import PermissionService


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user(*roles: UserRoleCode, is_superuser: bool = False):
    return SimpleNamespace(is_superuser=is_superuser, roles=[_role(role) for role in roles])


def test_redact_waybill_keeps_internal_remark_for_route_staff() -> None:
    data = {"internal_remark": "ops note", "quotation": "38.6"}

    redacted = PermissionService.redact_waybill(data.copy(), _user(UserRoleCode.ROUTE_STAFF))

    assert redacted["internal_remark"] == "ops note"
    assert redacted["quotation"] == "38.6"


def test_redact_waybill_hides_internal_remark_for_customs_staff() -> None:
    data = {"internal_remark": "ops note", "quotation": "38.6"}

    redacted = PermissionService.redact_waybill(data.copy(), _user(UserRoleCode.CUSTOMS_STAFF))

    assert redacted["internal_remark"] is None
    assert redacted["quotation"] == "38.6"


def test_redact_waybill_keeps_existing_customer_service_sensitive_redaction() -> None:
    data = {"internal_remark": "ops note", "quotation": "38.6", "data_charge": "10"}

    redacted = PermissionService.redact_waybill(data.copy(), _user(UserRoleCode.CUSTOMER_SERVICE))

    assert redacted["internal_remark"] is None
    assert redacted["quotation"] is None
    assert redacted["data_charge"] is None
