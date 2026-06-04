"""add warehouse receipt display order

Revision ID: 20260604_0031
Revises: 20260604_0030
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260604_0031"
down_revision: Union[str, None] = "20260604_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column("warehouse_receipts", "display_order"):
        op.add_column("warehouse_receipts", sa.Column("display_order", sa.Integer(), nullable=True))
    if not _has_index("warehouse_receipts", "idx_warehouse_receipts_display_order"):
        op.create_index("idx_warehouse_receipts_display_order", "warehouse_receipts", ["display_order"])


def downgrade() -> None:
    if _has_index("warehouse_receipts", "idx_warehouse_receipts_display_order"):
        op.drop_index("idx_warehouse_receipts_display_order", table_name="warehouse_receipts")
    if _has_column("warehouse_receipts", "display_order"):
        op.drop_column("warehouse_receipts", "display_order")
