from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode
from app.schemas.user import UserUpdate
from app.services.user_service import UserService


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.executed = []
        self.deleted = None

    def commit(self):
        self.committed = True

    def execute(self, statement):
        self.executed.append(statement)

    def delete(self, item):
        self.deleted = item


class FakeRepo:
    def __init__(self, users) -> None:
        self.users = {user.id: user for user in users}
        self.set_roles_calls = []

    def list(self, skip=0, limit=100):
        return list(self.users.values())[skip : skip + limit]

    def get(self, user_id: int):
        return self.users.get(user_id)

    def get_by_username(self, username: str):
        return next((user for user in self.users.values() if user.username == username), None)

    def set_roles(self, user, role_codes):
        self.set_roles_calls.append((user.id, role_codes))
        user.roles = [_role(code) for code in role_codes]


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user(user_id: int, username: str, roles: list[UserRoleCode], *, is_superuser: bool = False, active: bool = True):
    return SimpleNamespace(
        id=user_id,
        username=username,
        display_name=username,
        email=None,
        phone=None,
        is_active=active,
        is_superuser=is_superuser,
        roles=[_role(code) for code in roles],
    )


def _service(users):
    service = UserService.__new__(UserService)
    service.db = FakeDb()
    service.repo = FakeRepo(users)
    return service


def test_route_staff_lists_non_admin_peer_and_supported_roles() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    admin = _user(2, "admin", [UserRoleCode.ADMIN])
    customer = _user(3, "customer", [UserRoleCode.CUSTOMER_SERVICE])
    customs = _user(4, "customs", [UserRoleCode.CUSTOMS_STAFF])
    no_role = _user(5, "guest", [])
    service = _service([route, admin, customer, customs, no_role])

    result = service.list_users(route)

    assert [user.username for user in result] == ["route", "customer", "customs"]


def test_route_staff_can_update_customer_service_user() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    customer = _user(3, "customer", [UserRoleCode.CUSTOMER_SERVICE])
    service = _service([route, customer])

    result = service.update_user(
        3,
        UserUpdate(display_name="Customer A", role_codes=[UserRoleCode.CUSTOMS_STAFF]),
        route,
    )

    assert result.display_name == "Customer A"
    assert [role.code for role in result.roles] == [UserRoleCode.CUSTOMS_STAFF]
    assert service.db.committed is True


def test_route_staff_cannot_update_route_staff_peer() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    peer = _user(2, "peer", [UserRoleCode.ROUTE_STAFF])
    service = _service([route, peer])

    with pytest.raises(HTTPException) as exc_info:
        service.update_user(2, UserUpdate(display_name="Peer A"), route)

    assert exc_info.value.status_code == 403


def test_route_staff_cannot_assign_admin_role() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    customer = _user(3, "customer", [UserRoleCode.CUSTOMER_SERVICE])
    service = _service([route, customer])

    with pytest.raises(HTTPException) as exc_info:
        service.update_user(3, UserUpdate(role_codes=[UserRoleCode.ADMIN]), route)

    assert exc_info.value.status_code == 403


def test_route_staff_can_disable_customs_user() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    customs = _user(4, "customs", [UserRoleCode.CUSTOMS_STAFF])
    service = _service([route, customs])

    result = service.set_active(4, False, route)

    assert result.is_active is False
    assert service.db.committed is True


def test_admin_can_delete_user() -> None:
    admin = _user(1, "admin", [UserRoleCode.ADMIN])
    route = _user(2, "route", [UserRoleCode.ROUTE_STAFF])
    service = _service([admin, route])

    service.delete_user(2, admin)

    assert service.db.deleted is route
    assert service.db.committed is True
    assert len(service.db.executed) > 0


def test_route_staff_can_delete_customer_service_user() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    customer = _user(3, "customer", [UserRoleCode.CUSTOMER_SERVICE])
    service = _service([route, customer])

    service.delete_user(3, route)

    assert service.db.deleted is customer
    assert service.db.committed is True


def test_route_staff_cannot_delete_route_staff_peer() -> None:
    route = _user(1, "route", [UserRoleCode.ROUTE_STAFF])
    peer = _user(2, "peer", [UserRoleCode.ROUTE_STAFF])
    service = _service([route, peer])

    with pytest.raises(HTTPException) as exc_info:
        service.delete_user(2, route)

    assert exc_info.value.status_code == 403
    assert service.db.deleted is None
    assert service.db.committed is False


def test_user_cannot_delete_self() -> None:
    admin = _user(1, "admin", [UserRoleCode.ADMIN])
    service = _service([admin])

    with pytest.raises(HTTPException) as exc_info:
        service.delete_user(1, admin)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "cannot_delete_self"
