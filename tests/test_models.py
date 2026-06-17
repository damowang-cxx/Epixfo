from datetime import date

import app.models.all
from app.core.database import Base
from app.models.enums import CarrierAdapterType, CarrierQueryMethod, UserRoleCode, WaybillLifecycleStatus
from app.models.waybill import AirWaybill, WaybillOfficialFlightSegment


def test_core_model_tables_are_registered() -> None:
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "user_table_preferences",
        "carriers",
        "carrier_prefix_mappings",
        "carrier_query_configs",
        "carrier_query_adapters",
        "consignees",
        "consignee_contacts",
        "consignee_notify_parties",
        "auto_flight_query_settings",
        "air_waybills",
        "waybill_plans",
        "waybill_official_flight_segments",
        "waybill_official_infos",
        "waybill_status_events",
        "waybill_assembly_events",
        "waybill_query_snapshots",
        "waybill_alerts",
        "waybill_boards",
        "waybill_prebookings",
        "waybill_airline_files",
        "waybill_customs_access_grants",
        "waybill_view_logs",
        "user_refresh_tokens",
        "user_login_logs",
        "user_presence_logs",
        "user_daily_online_stats",
        "audit_logs",
        "box_documents",
        "boxes",
        "box_items",
        "warehouse_receipts",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_business_enum_values_match_phase_one_design() -> None:
    assert UserRoleCode.ADMIN.value == "admin"
    assert UserRoleCode.ROUTE_STAFF.value == "route_staff"
    assert CarrierAdapterType.DEDICATED.value == "dedicated"
    assert CarrierAdapterType.GENERAL.value == "general"
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
    assert "board_id" in waybill_columns
    assert "customs_staff_id" in waybill_columns
    assert "customs_data_uploaded_at" in waybill_columns
    assert "customs_data_uploaded_by" in waybill_columns
    assert "outbound_date" in waybill_columns


def test_prebooking_table_has_outbound_date_column() -> None:
    prebooking_columns = Base.metadata.tables["waybill_prebookings"].columns

    assert "outbound_date" in prebooking_columns


def test_carrier_agent_table_is_not_bound_to_single_carrier() -> None:
    agent_columns = Base.metadata.tables["carrier_agents"].columns

    assert "carrier_code" not in agent_columns


def test_user_table_preferences_have_account_scoped_columns() -> None:
    preference_columns = Base.metadata.tables["user_table_preferences"].columns

    assert "user_id" in preference_columns
    assert "table_key" in preference_columns
    assert "column_order" in preference_columns


def test_carrier_query_adapters_have_type_and_order_columns() -> None:
    adapter_columns = Base.metadata.tables["carrier_query_adapters"].columns

    assert "adapter_code" in adapter_columns
    assert "display_name" in adapter_columns
    assert "adapter_type" in adapter_columns
    assert "query_method" in adapter_columns
    assert "enabled" in adapter_columns
    assert "display_order" in adapter_columns


def test_query_snapshots_have_adapter_type_column() -> None:
    snapshot_columns = Base.metadata.tables["waybill_query_snapshots"].columns

    assert "adapter_code" in snapshot_columns
    assert "adapter_type" in snapshot_columns


def test_waybill_airline_files_table_has_expected_columns() -> None:
    airline_file_columns = Base.metadata.tables["waybill_airline_files"].columns

    for column in [
        "waybill_id",
        "original_file_name",
        "stored_file_path",
        "file_hash",
        "file_size",
        "content_type",
        "extracted_waybill_no",
        "extraction_method",
        "uploaded_by",
        "uploaded_at",
    ]:
        assert column in airline_file_columns


def test_waybill_board_table_has_expected_columns() -> None:
    board_columns = Base.metadata.tables["waybill_boards"].columns

    for column in [
        "board_no",
        "actual_board_no",
        "consignee_contact_id",
        "consignee_text",
        "created_by",
        "updated_by",
    ]:
        assert column in board_columns


def test_boxes_table_has_warehouse_file_detail_columns() -> None:
    box_columns = Base.metadata.tables["boxes"].columns

    for column in [
        "warehouse_waybill_no",
        "goods_name",
        "quantity",
        "weight",
        "original_volume_info",
        "original_weight_volume_ratio",
        "volume",
        "weight_volume_ratio",
        "source_row_number",
        "warehouse_receipt_id",
        "is_general_cargo",
        "never_bound_direct_upload",
        "unbound_reason",
        "unbound_remark",
    ]:
        assert column in box_columns


def test_atomic_box_tables_have_expected_binding_columns() -> None:
    receipt_columns = Base.metadata.tables["warehouse_receipts"].columns
    item_columns = Base.metadata.tables["box_items"].columns

    assert "warehouse_no" in receipt_columns
    assert "waybill_id" in receipt_columns
    assert "prebooking_id" in receipt_columns
    assert "total_volume" in receipt_columns
    assert "box_id" in item_columns
    assert "warehouse_waybill_no" in item_columns


def test_import_side_effect_registers_models() -> None:
    assert app.models.all.AirWaybill.__tablename__ == "air_waybills"


def test_waybill_official_estimated_flight_date_uses_first_available_segment_date() -> None:
    waybill = AirWaybill(
        waybill_no="784-83707805",
        include_tc=False,
        notify_pickup=False,
        lifecycle_status=WaybillLifecycleStatus.CREATED,
        monitor_enabled=True,
        consecutive_query_failures=0,
    )
    waybill.official_flight_segments = [
        WaybillOfficialFlightSegment(segment_order=3, flight_date=date(2026, 5, 13), raw_data={}),
        WaybillOfficialFlightSegment(segment_order=1, flight_date=None, raw_data={}),
        WaybillOfficialFlightSegment(segment_order=2, flight_date=date(2026, 5, 12), raw_data={}),
    ]

    assert waybill.official_estimated_flight_date == date(2026, 5, 12)


def test_waybill_official_estimated_flight_date_is_none_without_scraped_dates() -> None:
    waybill = AirWaybill(
        waybill_no="784-83707805",
        include_tc=False,
        notify_pickup=False,
        lifecycle_status=WaybillLifecycleStatus.CREATED,
        monitor_enabled=True,
        consecutive_query_failures=0,
    )

    assert waybill.official_estimated_flight_date is None
