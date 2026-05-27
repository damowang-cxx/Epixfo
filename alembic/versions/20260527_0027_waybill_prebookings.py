"""add waybill prebookings

Revision ID: 20260527_0027
Revises: 20260527_0026
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260527_0027"
down_revision: Union[str, None] = "20260527_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("waybill_prebookings"):
        op.create_table(
            "waybill_prebookings",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
            sa.Column("carrier_agent_id", sa.BigInteger(), nullable=False),
            sa.Column("agent", sa.String(length=128), nullable=True),
            sa.Column("planned_flight_date", sa.Date(), nullable=False),
            sa.Column("booked_volume", sa.Numeric(12, 3), nullable=False),
            sa.Column("waybill_no", sa.String(length=64), nullable=True),
            sa.Column("departure_port", sa.String(length=16), nullable=True),
            sa.Column("destination_port", sa.String(length=16), nullable=True),
            sa.Column("planned_flight_no", sa.String(length=32), nullable=True),
            sa.Column("planned_route_text", sa.String(length=255), nullable=True),
            sa.Column("consignee", sa.String(length=255), nullable=True),
            sa.Column("consignee_contact_id", sa.BigInteger(), nullable=True),
            sa.Column("customs_staff_id", sa.BigInteger(), nullable=True),
            sa.Column("data_charge", sa.Numeric(12, 2), nullable=True),
            sa.Column("delivery_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("document_cutoff_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("booked_weight", sa.Numeric(12, 3), nullable=True),
            sa.Column("density", sa.Numeric(12, 3), nullable=True),
            sa.Column("quotation", sa.String(length=64), nullable=True),
            sa.Column("include_tc", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("warehouse_data_remark", sa.Text(), nullable=True),
            sa.Column("notify_pickup", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("pickup_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("internal_remark", sa.Text(), nullable=True),
            sa.Column("customer_remark", sa.Text(), nullable=True),
            sa.Column("air_freight_cost", sa.Numeric(12, 2), nullable=True),
            sa.Column("other_charge", sa.Numeric(12, 2), nullable=True),
            sa.Column("payment_date", sa.Date(), nullable=True),
            sa.Column("converted_waybill_id", sa.BigInteger(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["carrier_agent_id"], ["carrier_agents.id"]),
            sa.ForeignKeyConstraint(["consignee_contact_id"], ["consignee_contacts.id"]),
            sa.ForeignKeyConstraint(["converted_waybill_id"], ["air_waybills.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["customs_staff_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_waybill_prebookings_status", "waybill_prebookings", ["status"])
        op.create_index("idx_waybill_prebookings_flight_date", "waybill_prebookings", ["planned_flight_date"])
        op.create_index("idx_waybill_prebookings_agent_id", "waybill_prebookings", ["carrier_agent_id"])
        op.create_index(
            "idx_waybill_prebookings_converted_waybill_id",
            "waybill_prebookings",
            ["converted_waybill_id"],
        )

    if not _has_column("warehouse_receipts", "prebooking_id"):
        op.add_column("warehouse_receipts", sa.Column("prebooking_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            "fk_warehouse_receipts_prebooking_id_waybill_prebookings",
            "warehouse_receipts",
            "waybill_prebookings",
            ["prebooking_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("idx_warehouse_receipts_prebooking_id", "warehouse_receipts", ["prebooking_id"])


def downgrade() -> None:
    if _has_column("warehouse_receipts", "prebooking_id"):
        op.drop_index("idx_warehouse_receipts_prebooking_id", table_name="warehouse_receipts")
        op.drop_constraint(
            "fk_warehouse_receipts_prebooking_id_waybill_prebookings",
            "warehouse_receipts",
            type_="foreignkey",
        )
        op.drop_column("warehouse_receipts", "prebooking_id")

    if _has_table("waybill_prebookings"):
        op.drop_index("idx_waybill_prebookings_converted_waybill_id", table_name="waybill_prebookings")
        op.drop_index("idx_waybill_prebookings_agent_id", table_name="waybill_prebookings")
        op.drop_index("idx_waybill_prebookings_flight_date", table_name="waybill_prebookings")
        op.drop_index("idx_waybill_prebookings_status", table_name="waybill_prebookings")
        op.drop_table("waybill_prebookings")
