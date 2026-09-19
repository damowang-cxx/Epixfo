from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, load_only, raiseload, selectinload

from app.models import AirWaybill, WarehouseReceipt
from app.schemas.waybill import WaybillWarehouseReceiptOut
from app.services.warehouse_planner_service import _needs_warehouse_planning_clause


def test_waybill_receipts_include_all_current_bindings_and_exclude_unbound_files():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE air_waybills (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE warehouse_receipts (id INTEGER PRIMARY KEY, waybill_id INTEGER, warehouse_no TEXT)")
        connection.exec_driver_sql("INSERT INTO air_waybills VALUES (7), (8)")
        connection.exec_driver_sql("INSERT INTO warehouse_receipts VALUES (1, 7, 'WH-A'), (2, 7, 'WH-B'), (3, NULL, 'WH-C'), (4, 8, 'WH-D')")
    query = select(AirWaybill).where(AirWaybill.id == 7).options(
        load_only(AirWaybill.id), raiseload("*"),
        selectinload(AirWaybill.warehouse_receipts).load_only(WarehouseReceipt.id, WarehouseReceipt.warehouse_no),
    )
    with Session(engine) as session:
        waybill = session.scalar(query)
        assert [WaybillWarehouseReceiptOut.model_validate(item).model_dump() for item in waybill.warehouse_receipts] == [
            {"id": 1, "warehouse_no": "WH-A"}, {"id": 2, "warehouse_no": "WH-B"},
        ]
        session.connection().exec_driver_sql("UPDATE warehouse_receipts SET waybill_id = NULL WHERE id = 2")
        session.expire_all()
        assert [item.warehouse_no for item in session.scalar(query).warehouse_receipts] == ["WH-A"]
        session.connection().exec_driver_sql("UPDATE warehouse_receipts SET waybill_id = NULL WHERE id = 1")
        session.expire_all()
        assert session.scalar(query).warehouse_receipts == []
    engine.dispose()


def test_waybill_returns_to_planner_candidates_after_last_receipt_is_unbound():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE air_waybills (id INTEGER PRIMARY KEY, outbound_date DATE)")
        connection.exec_driver_sql("CREATE TABLE warehouse_receipts (id INTEGER PRIMARY KEY, waybill_id INTEGER, warehouse_no TEXT)")
        connection.exec_driver_sql("INSERT INTO air_waybills VALUES (1, '2026-09-20'), (2, NULL), (3, '2026-09-20')")
        connection.exec_driver_sql("INSERT INTO warehouse_receipts VALUES (1, 1, 'WH-A'), (2, 2, 'WH-B')")

    candidate_query = select(AirWaybill.id).where(_needs_warehouse_planning_clause()).order_by(AirWaybill.id)
    with Session(engine) as session:
        assert list(session.scalars(candidate_query)) == [2, 3]
        session.connection().exec_driver_sql("UPDATE warehouse_receipts SET waybill_id = NULL WHERE id = 1")
        assert list(session.scalars(candidate_query)) == [1, 2, 3]
    engine.dispose()
