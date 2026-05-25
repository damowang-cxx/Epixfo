"""add customs waybill access and view logs

Revision ID: 20260525_0023
Revises: 20260525_0022
Create Date: 2026-05-25 12:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260525_0023"
down_revision: Union[str, None] = "20260525_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_column("air_waybills", "customs_staff_id"):
        op.add_column("air_waybills", sa.Column("customs_staff_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            "fk_air_waybills_customs_staff_id_users",
            "air_waybills",
            "users",
            ["customs_staff_id"],
            ["id"],
        )
        op.create_index("idx_air_waybills_customs_staff_id", "air_waybills", ["customs_staff_id"])

    if not _has_table("waybill_customs_access_grants"):
        op.create_table(
            "waybill_customs_access_grants",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("waybill_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("waybill_id", "user_id", name="uq_waybill_customs_access_grant"),
        )
        op.create_index("idx_waybill_customs_access_grants_waybill_id", "waybill_customs_access_grants", ["waybill_id"])
        op.create_index("idx_waybill_customs_access_grants_user_id", "waybill_customs_access_grants", ["user_id"])

    if not _has_table("waybill_view_logs"):
        op.create_table(
            "waybill_view_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("waybill_id", sa.BigInteger(), nullable=True),
            sa.Column("waybill_no", sa.String(length=64), nullable=False),
            sa.Column(
                "lifecycle_status",
                postgresql.ENUM(
                    "created",
                    "waiting_monitor",
                    "monitoring",
                    "warehouse_received",
                    "loaded",
                    "departed",
                    "arrived",
                    "pickup_notified",
                    "picked_up",
                    "voided",
                    name="waybill_lifecycle_status",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="SET NULL"),
        )
        op.create_index("idx_waybill_view_logs_user_id", "waybill_view_logs", ["user_id"])
        op.create_index("idx_waybill_view_logs_waybill_id", "waybill_view_logs", ["waybill_id"])
        op.create_index("idx_waybill_view_logs_viewed_at", "waybill_view_logs", ["viewed_at"])


def downgrade() -> None:
    if _has_table("waybill_view_logs"):
        op.drop_index("idx_waybill_view_logs_viewed_at", table_name="waybill_view_logs")
        op.drop_index("idx_waybill_view_logs_waybill_id", table_name="waybill_view_logs")
        op.drop_index("idx_waybill_view_logs_user_id", table_name="waybill_view_logs")
        op.drop_table("waybill_view_logs")

    if _has_table("waybill_customs_access_grants"):
        op.drop_index("idx_waybill_customs_access_grants_user_id", table_name="waybill_customs_access_grants")
        op.drop_index("idx_waybill_customs_access_grants_waybill_id", table_name="waybill_customs_access_grants")
        op.drop_table("waybill_customs_access_grants")

    if _has_column("air_waybills", "customs_staff_id"):
        op.drop_index("idx_air_waybills_customs_staff_id", table_name="air_waybills")
        op.drop_constraint("fk_air_waybills_customs_staff_id_users", "air_waybills", type_="foreignkey")
        op.drop_column("air_waybills", "customs_staff_id")
