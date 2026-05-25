"""add customs upload confirmation fields

Revision ID: 20260525_0024
Revises: 20260525_0023
Create Date: 2026-05-25 18:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0024"
down_revision: Union[str, None] = "20260525_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_fk(table_name: str, fk_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    if not _has_column("air_waybills", "customs_data_uploaded_at"):
        op.add_column("air_waybills", sa.Column("customs_data_uploaded_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_column("air_waybills", "customs_data_uploaded_by"):
        op.add_column("air_waybills", sa.Column("customs_data_uploaded_by", sa.BigInteger(), nullable=True))

    if not _has_fk("air_waybills", "fk_air_waybills_customs_data_uploaded_by_users"):
        op.create_foreign_key(
            "fk_air_waybills_customs_data_uploaded_by_users",
            "air_waybills",
            "users",
            ["customs_data_uploaded_by"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_index("air_waybills", "idx_air_waybills_customs_data_uploaded_by"):
        op.create_index("idx_air_waybills_customs_data_uploaded_by", "air_waybills", ["customs_data_uploaded_by"])
    if not _has_index("air_waybills", "idx_air_waybills_customs_data_uploaded_at"):
        op.create_index("idx_air_waybills_customs_data_uploaded_at", "air_waybills", ["customs_data_uploaded_at"])


def downgrade() -> None:
    if _has_index("air_waybills", "idx_air_waybills_customs_data_uploaded_at"):
        op.drop_index("idx_air_waybills_customs_data_uploaded_at", table_name="air_waybills")
    if _has_index("air_waybills", "idx_air_waybills_customs_data_uploaded_by"):
        op.drop_index("idx_air_waybills_customs_data_uploaded_by", table_name="air_waybills")
    if _has_fk("air_waybills", "fk_air_waybills_customs_data_uploaded_by_users"):
        op.drop_constraint("fk_air_waybills_customs_data_uploaded_by_users", "air_waybills", type_="foreignkey")
    if _has_column("air_waybills", "customs_data_uploaded_by"):
        op.drop_column("air_waybills", "customs_data_uploaded_by")
    if _has_column("air_waybills", "customs_data_uploaded_at"):
        op.drop_column("air_waybills", "customs_data_uploaded_at")
