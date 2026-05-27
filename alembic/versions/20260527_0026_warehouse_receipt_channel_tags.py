"""add warehouse receipt channel tags

Revision ID: 20260527_0026
Revises: 20260525_0025
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260527_0026"
down_revision: Union[str, None] = "20260525_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("warehouse_receipts", "channel_tags"):
        op.add_column(
            "warehouse_receipts",
            sa.Column(
                "channel_tags",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    if _has_column("warehouse_receipts", "channel_tags"):
        op.drop_column("warehouse_receipts", "channel_tags")
