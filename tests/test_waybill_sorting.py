from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.waybills import router
from app.core.database import get_db
from app.models import AirWaybill
from app.repositories.waybill_repository import WaybillRepository
from app.services.waybill_service import WaybillService


@pytest.fixture
def repo():
    # Only sorting/filtering columns are needed; production JSONB tables stay untouched.
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE air_waybills (
                id INTEGER PRIMARY KEY, created_at DATETIME, board_id INTEGER,
                destination_port TEXT, lifecycle_status TEXT
            )
        """)
        connection.exec_driver_sql("""
            CREATE TABLE waybill_plans (
                id INTEGER PRIMARY KEY, waybill_id INTEGER UNIQUE,
                planned_flight_date DATE, planned_flight_no TEXT
            )
        """)
        connection.exec_driver_sql("""
            INSERT INTO air_waybills VALUES
                (1, '2026-09-19 12:00:00', 1, 'AMS', 'picked_up'),
                (2, '2026-09-18 12:00:00', 1, 'AMS', 'created'),
                (3, '2026-09-17 12:00:00', NULL, 'LHR', 'created'),
                (4, '2026-09-18 12:00:00', NULL, 'AMS', 'voided'),
                (5, '2026-09-16 12:00:00', NULL, 'AMS', 'created'),
                (6, '2026-09-15 12:00:00', NULL, 'AMS', 'created')
        """)
        connection.exec_driver_sql("""
            INSERT INTO waybill_plans VALUES
                (1, 1, '2026-09-22', 'QR123'),
                (2, 2, '2026-09-20', 'QR123'),
                (3, 3, '2026-09-21', 'QR123'),
                (4, 4, '2026-09-20', 'QR123'),
                (5, 5, NULL, 'QR123')
        """)
    with Session(engine) as session:
        yield WaybillRepository(session)
    engine.dispose()


def test_default_order_is_creation_time_not_id_status_board_or_flight_date(repo):
    query = select(AirWaybill.id).order_by(AirWaybill.id.asc())
    assert repo.list_filtered(query, 0, 20) == [1, 4, 2, 3, 5, 6]


@pytest.mark.parametrize("sort,expected", [
    ("planned_flight_date_asc", [4, 2, 3, 1, 5, 6]),
    ("planned_flight_date_desc", [1, 3, 4, 2, 5, 6]),
])
def test_flight_date_order_uses_each_waybill_date_and_keeps_empty_dates_last(repo, sort, expected):
    assert repo.list_filtered(select(AirWaybill.id), 0, 20, sort=sort) == expected


@pytest.mark.parametrize("sort,expected", [
    ("created_at_desc", [1, 4, 2, 3, 5, 6]),
    ("planned_flight_date_asc", [4, 2, 3, 1, 5, 6]),
    ("planned_flight_date_desc", [1, 3, 4, 2, 5, 6]),
])
def test_sort_applies_before_pagination_without_duplicates(repo, sort, expected):
    pages = [repo.list_filtered(select(AirWaybill.id), offset, 2, sort=sort) for offset in (0, 2, 4)]
    assert [item for page in pages for item in page] == expected


def test_sort_preserves_destination_and_date_filters_without_duplicate_join(repo):
    query = repo.apply_filters(select(AirWaybill.id), destination_port="AMS", planned_flight_no="QR123",
                               planned_flight_date_from=date(2026, 9, 20), planned_flight_date_to=date(2026, 9, 21))
    assert repo.list_filtered(query, 0, 20, sort="planned_flight_date_desc") == [4, 2]
    assert repo.count_filtered(query) == 2


@pytest.mark.parametrize("date_from,date_to,expected", [
    (date(2026, 9, 21), None, [1, 3]),
    (None, date(2026, 9, 20), [4, 2]),
    (date(2026, 9, 20), date(2026, 9, 21), [4, 2, 3]),
])
def test_planned_flight_date_range_is_inclusive_and_supports_open_ends(repo, date_from, date_to, expected):
    query = repo.apply_filters(
        select(AirWaybill.id),
        planned_flight_date_from=date_from,
        planned_flight_date_to=date_to,
    )
    assert repo.list_filtered(query, 0, 20) == expected


def test_service_forwards_sort_and_pagination(repo):
    service = WaybillService.__new__(WaybillService)
    service.repo = repo
    repo.base_query = lambda: select(AirWaybill.id)
    user = SimpleNamespace(is_superuser=True)
    items, total, page, page_size = service.list(user, page=2, page_size=2, sort="planned_flight_date_asc")
    assert (items, total, page, page_size) == ([3, 1], 6, 2, 2)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_superuser=True)
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("sort", [None, "planned_flight_date_asc", "planned_flight_date_desc"])
def test_api_accepts_sort_and_defaults_to_newest(client, sort):
    with patch.object(WaybillService, "list", return_value=([], 0, 1, 20)) as listing:
        response = client.get("/waybills", params={"sort": sort} if sort else {})
    assert response.status_code == 200
    assert listing.call_args.kwargs["sort"] == (sort or "created_at_desc")


def test_api_rejects_unknown_sort(client):
    with patch.object(WaybillService, "list") as listing:
        assert client.get("/waybills", params={"sort": "arbitrary_column"}).status_code == 422
    listing.assert_not_called()


def test_api_forwards_planned_flight_date_range(client):
    with patch.object(WaybillService, "list", return_value=([], 0, 1, 20)) as listing:
        response = client.get("/waybills", params={
            "planned_flight_date_from": "2026-09-20",
            "planned_flight_date_to": "2026-09-22",
        })
    assert response.status_code == 200
    assert listing.call_args.kwargs["planned_flight_date_from"] == date(2026, 9, 20)
    assert listing.call_args.kwargs["planned_flight_date_to"] == date(2026, 9, 22)


@pytest.mark.parametrize("field", ["planned_flight_date_from", "planned_flight_date_to"])
def test_api_rejects_invalid_planned_flight_dates(client, field):
    with patch.object(WaybillService, "list") as listing:
        response = client.get("/waybills", params={field: "2026-02-30"})
    assert response.status_code == 422
    listing.assert_not_called()
