import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.user import User, UserTablePreference
from app.schemas.user_preference import TableColumnPreferenceIn
from app.services.user_preference_service import UserPreferenceService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    original_id_type = UserTablePreference.__table__.c.id.type
    UserTablePreference.__table__.c.id.type = Integer()
    try:
        Base.metadata.create_all(engine, tables=[User.__table__, UserTablePreference.__table__])
    finally:
        UserTablePreference.__table__.c.id.type = original_id_type
    SessionLocal = sessionmaker(bind=engine, class_=Session)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _add_user(db: Session, user_id: int, username: str) -> User:
    user = User(id=user_id, username=username, password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_table_column_preference_defaults_to_empty_order(db_session: Session) -> None:
    user = _add_user(db_session, 1, "admin")

    preference = UserPreferenceService(db_session).get_table_columns(user, "waybills:list")

    assert preference.table_key == "waybills:list"
    assert preference.column_order == []


def test_table_column_preference_is_saved_per_user(db_session: Session) -> None:
    first_user = _add_user(db_session, 1, "first")
    second_user = _add_user(db_session, 2, "second")
    service = UserPreferenceService(db_session)

    service.set_table_columns(
        first_user,
        "waybills:list",
        TableColumnPreferenceIn(column_order=["agent", "waybill_no"]),
    )

    assert service.get_table_columns(first_user, "waybills:list").column_order == ["agent", "waybill_no"]
    assert service.get_table_columns(second_user, "waybills:list").column_order == []


def test_table_column_preference_overwrites_existing_order(db_session: Session) -> None:
    user = _add_user(db_session, 1, "admin")
    service = UserPreferenceService(db_session)

    service.set_table_columns(
        user,
        "waybills:list",
        TableColumnPreferenceIn(column_order=["agent", "waybill_no"]),
    )
    service.set_table_columns(
        user,
        "waybills:list",
        TableColumnPreferenceIn(column_order=["customs_staff"]),
    )

    assert service.get_table_columns(user, "waybills:list").column_order == ["customs_staff"]
