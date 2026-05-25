from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models.all  # noqa: F401
from app.core.database import Base
from app.models.enums import UserRoleCode
from app.models.presence import UserDailyOnlineStats, UserLoginLog, UserPresenceLog
from app.models.user import Role, User, UserRole
from app.services import presence_service as presence_module
from app.services.presence_service import PresenceService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    postgres_defaults = [
        (UserLoginLog.__table__.c.login_at, UserLoginLog.__table__.c.login_at.server_default),
        (UserPresenceLog.__table__.c.heartbeat_at, UserPresenceLog.__table__.c.heartbeat_at.server_default),
    ]
    for column, _default in postgres_defaults:
        column.server_default = None
    sqlite_integer_ids = [
        (UserPresenceLog.__table__.c.id, UserPresenceLog.__table__.c.id.type),
        (UserDailyOnlineStats.__table__.c.id, UserDailyOnlineStats.__table__.c.id.type),
    ]
    for column, _type in sqlite_integer_ids:
        column.type = Integer()
    try:
        Base.metadata.create_all(
            engine,
            tables=[
                User.__table__,
                Role.__table__,
                UserRole.__table__,
                UserLoginLog.__table__,
                UserPresenceLog.__table__,
                UserDailyOnlineStats.__table__,
            ],
        )
    finally:
        for column, default in postgres_defaults:
            column.server_default = default
        for column, column_type in sqlite_integer_ids:
            column.type = column_type
    SessionLocal = sessionmaker(bind=engine, class_=Session)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_roles(db: Session) -> dict[UserRoleCode, Role]:
    roles = {
        UserRoleCode.ADMIN: Role(id=1, code=UserRoleCode.ADMIN, name="管理员"),
        UserRoleCode.ROUTE_STAFF: Role(id=2, code=UserRoleCode.ROUTE_STAFF, name="航线"),
        UserRoleCode.CUSTOMER_SERVICE: Role(id=3, code=UserRoleCode.CUSTOMER_SERVICE, name="客服"),
        UserRoleCode.CUSTOMS_STAFF: Role(id=4, code=UserRoleCode.CUSTOMS_STAFF, name="清关"),
    }
    db.add_all(roles.values())
    db.flush()
    return roles


def _add_user(
    db: Session,
    user_id: int,
    username: str,
    role: Role,
    last_seen_at: datetime | None,
    *,
    is_active: bool = True,
    last_login_at: datetime | None = None,
) -> User:
    user = User(
        id=user_id,
        username=username,
        password_hash="hash",
        display_name=username.upper(),
        is_active=is_active,
        is_superuser=False,
        last_seen_at=last_seen_at,
        last_login_at=last_login_at,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(id=user_id, user_id=user_id, role_id=role.id))
    db.commit()
    return user


def test_user_statuses_sort_online_first_then_role_rank(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 22, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(presence_module, "utc_now", lambda: now)
    roles = _seed_roles(db_session)
    _add_user(db_session, 1, "offline-admin", roles[UserRoleCode.ADMIN], now - timedelta(minutes=5))
    _add_user(db_session, 2, "online-customs", roles[UserRoleCode.CUSTOMS_STAFF], now - timedelta(seconds=30))
    _add_user(db_session, 3, "online-route", roles[UserRoleCode.ROUTE_STAFF], now - timedelta(seconds=90))
    _add_user(db_session, 4, "disabled-admin", roles[UserRoleCode.ADMIN], now - timedelta(seconds=10), is_active=False)
    _add_user(db_session, 5, "offline-cs", roles[UserRoleCode.CUSTOMER_SERVICE], None)

    statuses = PresenceService(db_session).user_statuses()

    assert [item["username"] for item in statuses] == [
        "online-route",
        "online-customs",
        "disabled-admin",
        "offline-admin",
        "offline-cs",
    ]
    assert statuses[0]["online"] is True
    assert statuses[2]["status"] == "disabled"
    assert statuses[2]["online"] is False


def test_heartbeat_uses_two_minute_continuity_window(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 22, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(presence_module, "utc_now", lambda: now)
    monkeypatch.setattr(presence_module, "local_now", lambda: now)
    roles = _seed_roles(db_session)
    user = _add_user(db_session, 1, "admin", roles[UserRoleCode.ADMIN], now - timedelta(seconds=119))

    PresenceService(db_session).heartbeat(user, "127.0.0.1", "pytest")

    stat = db_session.query(UserDailyOnlineStats).filter_by(user_id=user.id).one()
    assert stat.total_online_seconds == 119

    user.last_seen_at = now - timedelta(seconds=121)
    db_session.commit()
    PresenceService(db_session).heartbeat(user, "127.0.0.1", "pytest")

    stat = db_session.query(UserDailyOnlineStats).filter_by(user_id=user.id).one()
    assert stat.total_online_seconds == 119


def test_user_sessions_mark_current_online_and_logout(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 22, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(presence_module, "utc_now", lambda: now)
    roles = _seed_roles(db_session)
    user = _add_user(db_session, 1, "admin", roles[UserRoleCode.ADMIN], now - timedelta(seconds=20))
    db_session.add_all(
        [
            UserLoginLog(
                id=1,
                user_id=user.id,
                login_at=now - timedelta(hours=1),
                logout_at=now - timedelta(minutes=30),
                ip_address="10.0.0.1",
                user_agent="browser-a",
            ),
            UserLoginLog(
                id=2,
                user_id=user.id,
                login_at=now - timedelta(minutes=10),
                logout_at=None,
                ip_address="10.0.0.2",
                user_agent="browser-b",
            ),
        ]
    )
    db_session.commit()

    sessions = PresenceService(db_session).user_sessions(user.id, 30)

    assert sessions[0]["id"] == 2
    assert sessions[0]["status"] == "online"
    assert sessions[0]["effective_logout_at"] is None
    assert sessions[0]["duration_seconds"] == 600
    assert sessions[1]["status"] == "logged_out"
    assert sessions[1]["duration_seconds"] == 1800


def test_user_sessions_mark_open_log_as_timeout_with_last_seen(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 22, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(presence_module, "utc_now", lambda: now)
    roles = _seed_roles(db_session)
    user = _add_user(db_session, 1, "admin", roles[UserRoleCode.ADMIN], now - timedelta(minutes=10))
    db_session.add(
        UserLoginLog(
            id=1,
            user_id=user.id,
            login_at=now - timedelta(hours=1),
            logout_at=None,
            ip_address="10.0.0.1",
            user_agent="browser-a",
        )
    )
    db_session.commit()

    sessions = PresenceService(db_session).user_sessions(user.id, 30)

    assert sessions[0]["status"] == "timeout"
    assert sessions[0]["effective_logout_at"] == now - timedelta(minutes=10)
    assert sessions[0]["duration_seconds"] == 3000
