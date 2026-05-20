import app.models.all
from app.core.database import Base
from app.models.enums import CarrierQueryMethod, UserRoleCode, WaybillLifecycleStatus


def test_core_model_tables_are_registered() -> None:
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "carriers",
        "carrier_prefix_mappings",
        "carrier_query_configs",
        "air_waybills",
        "waybill_plans",
        "waybill_official_flight_segments",
        "waybill_official_infos",
        "waybill_status_events",
        "waybill_assembly_events",
        "waybill_query_snapshots",
        "waybill_alerts",
        "user_refresh_tokens",
        "user_login_logs",
        "user_presence_logs",
        "user_daily_online_stats",
        "audit_logs",
        "box_documents",
        "boxes",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_business_enum_values_match_phase_one_design() -> None:
    assert UserRoleCode.ADMIN.value == "admin"
    assert UserRoleCode.ROUTE_STAFF.value == "route_staff"
    assert CarrierQueryMethod.HYBRID.value == "hybrid"
    assert WaybillLifecycleStatus.WAREHOUSE_RECEIVED.value == "warehouse_received"
    assert WaybillLifecycleStatus.PICKED_UP.value == "picked_up"


def test_waybill_table_has_monitoring_columns() -> None:
    waybill_columns = Base.metadata.tables["air_waybills"].columns

    assert "lifecycle_status" in waybill_columns
    assert "monitor_enabled" in waybill_columns
    assert "first_monitor_at" in waybill_columns
    assert "next_query_at" in waybill_columns
    assert "consecutive_query_failures" in waybill_columns


def test_import_side_effect_registers_models() -> None:
    assert app.models.all.AirWaybill.__tablename__ == "air_waybills"
