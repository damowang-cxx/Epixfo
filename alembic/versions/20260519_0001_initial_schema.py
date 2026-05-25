"""initial schema

Revision ID: 20260519_0001
Revises:
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260519_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_code = postgresql.ENUM(
    "admin",
    "route_staff",
    "customer_service",
    "customs_staff",
    name="user_role_code",
    create_type=False,
)
waybill_lifecycle_status = postgresql.ENUM(
    "created",
    "waiting_monitor",
    "monitoring",
    "warehouse_received",
    "loaded",
    "departed",
    "arrived",
    "pickup_notified",
    "picked_up",
    "closed",
    "voided",
    name="waybill_lifecycle_status",
    create_type=False,
)
carrier_query_method = postgresql.ENUM(
    "protocol",
    "playwright",
    "hybrid",
    name="carrier_query_method",
    create_type=False,
)
query_status = postgresql.ENUM(
    "success",
    "failed",
    "partial_success",
    name="query_status",
    create_type=False,
)
alert_level = postgresql.ENUM(
    "info",
    "warning",
    "critical",
    name="alert_level",
    create_type=False,
)
alert_status = postgresql.ENUM(
    "active",
    "acknowledged",
    "resolved",
    "ignored",
    name="alert_status",
    create_type=False,
)
official_event_type = postgresql.ENUM(
    "waybill_received",
    "cargo_received",
    "origin_cargo_received",
    "cargo_loaded",
    "flight_departed",
    "flight_arrived",
    "transit_received",
    "destination_received",
    "pickup_notified",
    "picked_up",
    "cargo_assembled",
    "unknown",
    name="official_event_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE user_role_code AS ENUM ('admin', 'route_staff', 'customer_service', 'customs_staff')")
    op.execute(
        "CREATE TYPE waybill_lifecycle_status AS ENUM ("
        "'created', 'waiting_monitor', 'monitoring', 'warehouse_received', 'loaded', "
        "'departed', 'arrived', 'pickup_notified', 'picked_up', 'closed', 'voided'"
        ")"
    )
    op.execute("CREATE TYPE carrier_query_method AS ENUM ('protocol', 'playwright', 'hybrid')")
    op.execute("CREATE TYPE query_status AS ENUM ('success', 'failed', 'partial_success')")
    op.execute("CREATE TYPE alert_level AS ENUM ('info', 'warning', 'critical')")
    op.execute("CREATE TYPE alert_status AS ENUM ('active', 'acknowledged', 'resolved', 'ignored')")
    op.execute(
        "CREATE TYPE official_event_type AS ENUM ("
        "'waybill_received', 'cargo_received', 'origin_cargo_received', 'cargo_loaded', "
        "'flight_departed', 'flight_arrived', 'transit_received', 'destination_received', "
        "'pickup_notified', 'picked_up', 'cargo_assembled', 'unknown'"
        ")"
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_users_is_active", "users", ["is_active"])
    op.create_index("idx_users_last_seen_at", "users", ["last_seen_at"])

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", user_role_code, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    op.create_table(
        "carriers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("carrier_code", sa.String(length=16), nullable=False),
        sa.Column("carrier_name", sa.String(length=128), nullable=False),
        sa.Column("carrier_name_en", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_code"),
    )

    op.create_table(
        "carrier_prefix_mappings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("carrier_code", sa.String(length=16), nullable=False),
        sa.Column("adapter_code", sa.String(length=64), nullable=False),
        sa.Column("query_method", carrier_query_method, server_default="hybrid", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carrier_code"], ["carriers.carrier_code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix"),
    )

    op.create_table(
        "carrier_query_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("carrier_code", sa.String(length=16), nullable=False),
        sa.Column("adapter_code", sa.String(length=64), nullable=False),
        sa.Column("query_method", carrier_query_method, nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default="60", nullable=False),
        sa.Column("max_retry", sa.Integer(), server_default="3", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carrier_code"], ["carriers.carrier_code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_code", "adapter_code", name="uq_carrier_query_config"),
    )

    op.create_table(
        "air_waybills",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_no", sa.String(length=64), nullable=False),
        sa.Column("carrier_prefix", sa.String(length=8), nullable=True),
        sa.Column("carrier_code", sa.String(length=16), nullable=True),
        sa.Column("destination_port", sa.String(length=16), nullable=True),
        sa.Column("agent", sa.String(length=128), nullable=True),
        sa.Column("warehouse_no", sa.String(length=128), nullable=True),
        sa.Column("consignee", sa.String(length=255), nullable=True),
        sa.Column("document_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("route_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("data_charge", sa.Numeric(12, 2), nullable=True),
        sa.Column("delivery_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_cutoff_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booked_weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("booked_volume", sa.Numeric(12, 3), nullable=True),
        sa.Column("density", sa.Numeric(12, 3), nullable=True),
        sa.Column("quotation", sa.Numeric(12, 2), nullable=True),
        sa.Column("include_tc", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("warehouse_data_remark", sa.Text(), nullable=True),
        sa.Column("notify_pickup", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pickup_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("internal_remark", sa.Text(), nullable=True),
        sa.Column("customer_remark", sa.Text(), nullable=True),
        sa.Column("air_freight_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("lifecycle_status", waybill_lifecycle_status, server_default="created", nullable=False),
        sa.Column("alert_level", alert_level, nullable=True),
        sa.Column("monitor_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("first_monitor_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_query_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_query_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_query_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carrier_code"], ["carriers.carrier_code"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["route_staff_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_no"),
    )
    op.create_index("idx_air_waybills_waybill_no", "air_waybills", ["waybill_no"])
    op.create_index("idx_air_waybills_carrier_code", "air_waybills", ["carrier_code"])
    op.create_index("idx_air_waybills_lifecycle_status", "air_waybills", ["lifecycle_status"])
    op.create_index("idx_air_waybills_next_query_at", "air_waybills", ["next_query_at"])
    op.create_index("idx_air_waybills_created_at", "air_waybills", ["created_at"])
    op.create_index("idx_air_waybills_route_staff_id", "air_waybills", ["route_staff_id"])

    op.create_table(
        "waybill_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("planned_flight_no", sa.String(length=32), nullable=True),
        sa.Column("planned_flight_date", sa.Date(), nullable=True),
        sa.Column("planned_destination", sa.String(length=16), nullable=True),
        sa.Column("planned_route_text", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_id"),
    )
    op.create_index("idx_waybill_plans_flight_date", "waybill_plans", ["planned_flight_date"])
    op.create_index("idx_waybill_plans_flight_no", "waybill_plans", ["planned_flight_no"])

    op.create_table(
        "waybill_query_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier_code", sa.String(length=16), nullable=True),
        sa.Column("adapter_code", sa.String(length=64), nullable=True),
        sa.Column("query_method", carrier_query_method, nullable=True),
        sa.Column("query_status", query_status, nullable=False),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queried_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_query_snapshots_waybill_id", "waybill_query_snapshots", ["waybill_id"])
    op.create_index("idx_query_snapshots_status", "waybill_query_snapshots", ["query_status"])
    op.create_index("idx_query_snapshots_queried_at", "waybill_query_snapshots", ["queried_at"])

    op.create_table(
        "waybill_official_flight_segments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("booking_no", sa.String(length=64), nullable=True),
        sa.Column("route_text", sa.String(length=255), nullable=True),
        sa.Column("segment_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("departure_airport", sa.String(length=16), nullable=True),
        sa.Column("arrival_airport", sa.String(length=16), nullable=True),
        sa.Column("flight_no", sa.String(length=32), nullable=True),
        sa.Column("flight_date", sa.Date(), nullable=True),
        sa.Column("pieces", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("volume", sa.Numeric(12, 3), nullable=True),
        sa.Column("booking_type", sa.String(length=32), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_official_segments_waybill_id", "waybill_official_flight_segments", ["waybill_id"])
    op.create_index("idx_official_segments_flight_no", "waybill_official_flight_segments", ["flight_no"])
    op.create_index("idx_official_segments_flight_date", "waybill_official_flight_segments", ["flight_date"])

    op.create_table(
        "waybill_official_infos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("official_waybill_no", sa.String(length=64), nullable=True),
        sa.Column("carrier_text", sa.String(length=128), nullable=True),
        sa.Column("route_text", sa.String(length=255), nullable=True),
        sa.Column("goods_name", sa.Text(), nullable=True),
        sa.Column("total_pieces", sa.Integer(), nullable=True),
        sa.Column("total_weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("total_volume", sa.Numeric(12, 3), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_id"),
    )

    op.create_table(
        "waybill_status_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("event_time_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("event_time_text", sa.String(length=128), nullable=True),
        sa.Column("event_city", sa.String(length=128), nullable=True),
        sa.Column("airport_code", sa.String(length=16), nullable=True),
        sa.Column("flight_no", sa.String(length=32), nullable=True),
        sa.Column("status_text", sa.Text(), nullable=False),
        sa.Column("normalized_event_type", official_event_type, server_default="unknown", nullable=False),
        sa.Column("pieces", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("event_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_id", "event_hash", name="uq_status_event_hash"),
    )
    op.create_index("idx_status_events_waybill_id", "waybill_status_events", ["waybill_id"])
    op.create_index("idx_status_events_type", "waybill_status_events", ["normalized_event_type"])
    op.create_index("idx_status_events_time", "waybill_status_events", ["event_time_local"])
    op.create_index("idx_status_events_flight_no", "waybill_status_events", ["flight_no"])

    op.create_table(
        "waybill_assembly_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("event_time_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("event_time_text", sa.String(length=128), nullable=True),
        sa.Column("event_city", sa.String(length=128), nullable=True),
        sa.Column("status_text", sa.Text(), nullable=False),
        sa.Column("uld_no", sa.String(length=64), nullable=True),
        sa.Column("pieces", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("event_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_id", "event_hash", name="uq_assembly_event_hash"),
    )

    op.create_table(
        "waybill_alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("alert_level", alert_level, server_default="warning", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("status", alert_status, server_default="active", nullable=False),
        sa.Column("acknowledged_by", sa.BigInteger(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_waybill_alerts_waybill_id", "waybill_alerts", ["waybill_id"])
    op.create_index("idx_waybill_alerts_status", "waybill_alerts", ["status"])
    op.create_index("idx_waybill_alerts_type", "waybill_alerts", ["alert_type"])
    op.create_index("idx_waybill_alerts_level", "waybill_alerts", ["alert_level"])
    op.create_index(
        "uq_active_alert_per_type",
        "waybill_alerts",
        ["waybill_id", "alert_type"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    roles_table = sa.table(
        "roles",
        sa.column("code", user_role_code),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        roles_table,
        [
            {"code": "admin", "name": "管理员", "description": "系统管理员"},
            {"code": "route_staff", "name": "航线排仓人员", "description": "运单录入与航班监控"},
            {"code": "customer_service", "name": "客服人员", "description": "查看已入仓及之后运单"},
            {"code": "customs_staff", "name": "清关人员", "description": "查看起飞前三天内运单"},
        ],
    )

    carriers_table = sa.table(
        "carriers",
        sa.column("carrier_code", sa.String),
        sa.column("carrier_name", sa.String),
        sa.column("carrier_name_en", sa.String),
    )
    op.bulk_insert(
        carriers_table,
        [{"carrier_code": "CZ", "carrier_name": "南方航空", "carrier_name_en": "China Southern Airlines"}],
    )

    prefix_mappings_table = sa.table(
        "carrier_prefix_mappings",
        sa.column("prefix", sa.String),
        sa.column("carrier_code", sa.String),
        sa.column("adapter_code", sa.String),
        sa.column("query_method", carrier_query_method),
    )
    op.bulk_insert(
        prefix_mappings_table,
        [{"prefix": "784", "carrier_code": "CZ", "adapter_code": "cz_adapter", "query_method": "hybrid"}],
    )

    query_configs_table = sa.table(
        "carrier_query_configs",
        sa.column("carrier_code", sa.String),
        sa.column("adapter_code", sa.String),
        sa.column("query_method", carrier_query_method),
        sa.column("remark", sa.Text),
    )
    op.bulk_insert(
        query_configs_table,
        [{"carrier_code": "CZ", "adapter_code": "cz_adapter", "query_method": "hybrid", "remark": "一期预置南航查询配置"}],
    )


def downgrade() -> None:
    op.drop_index("uq_active_alert_per_type", table_name="waybill_alerts")
    op.drop_index("idx_waybill_alerts_level", table_name="waybill_alerts")
    op.drop_index("idx_waybill_alerts_type", table_name="waybill_alerts")
    op.drop_index("idx_waybill_alerts_status", table_name="waybill_alerts")
    op.drop_index("idx_waybill_alerts_waybill_id", table_name="waybill_alerts")
    op.drop_table("waybill_alerts")
    op.drop_table("waybill_assembly_events")
    op.drop_index("idx_status_events_flight_no", table_name="waybill_status_events")
    op.drop_index("idx_status_events_time", table_name="waybill_status_events")
    op.drop_index("idx_status_events_type", table_name="waybill_status_events")
    op.drop_index("idx_status_events_waybill_id", table_name="waybill_status_events")
    op.drop_table("waybill_status_events")
    op.drop_table("waybill_official_infos")
    op.drop_index("idx_official_segments_flight_date", table_name="waybill_official_flight_segments")
    op.drop_index("idx_official_segments_flight_no", table_name="waybill_official_flight_segments")
    op.drop_index("idx_official_segments_waybill_id", table_name="waybill_official_flight_segments")
    op.drop_table("waybill_official_flight_segments")
    op.drop_index("idx_query_snapshots_queried_at", table_name="waybill_query_snapshots")
    op.drop_index("idx_query_snapshots_status", table_name="waybill_query_snapshots")
    op.drop_index("idx_query_snapshots_waybill_id", table_name="waybill_query_snapshots")
    op.drop_table("waybill_query_snapshots")
    op.drop_index("idx_waybill_plans_flight_no", table_name="waybill_plans")
    op.drop_index("idx_waybill_plans_flight_date", table_name="waybill_plans")
    op.drop_table("waybill_plans")
    op.drop_index("idx_air_waybills_route_staff_id", table_name="air_waybills")
    op.drop_index("idx_air_waybills_created_at", table_name="air_waybills")
    op.drop_index("idx_air_waybills_next_query_at", table_name="air_waybills")
    op.drop_index("idx_air_waybills_lifecycle_status", table_name="air_waybills")
    op.drop_index("idx_air_waybills_carrier_code", table_name="air_waybills")
    op.drop_index("idx_air_waybills_waybill_no", table_name="air_waybills")
    op.drop_table("air_waybills")
    op.drop_table("carrier_query_configs")
    op.drop_table("carrier_prefix_mappings")
    op.drop_table("carriers")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("idx_users_last_seen_at", table_name="users")
    op.drop_index("idx_users_is_active", table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE official_event_type")
    op.execute("DROP TYPE alert_status")
    op.execute("DROP TYPE alert_level")
    op.execute("DROP TYPE query_status")
    op.execute("DROP TYPE carrier_query_method")
    op.execute("DROP TYPE waybill_lifecycle_status")
    op.execute("DROP TYPE user_role_code")
