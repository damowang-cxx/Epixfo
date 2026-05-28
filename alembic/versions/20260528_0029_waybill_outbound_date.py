"""add outbound date to waybills and prebookings

Revision ID: 20260528_0029
Revises: 20260528_0028
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_0029"
down_revision: Union[str, None] = "20260528_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("air_waybills", "outbound_date"):
        op.add_column("air_waybills", sa.Column("outbound_date", sa.Date(), nullable=True))
    if not _has_column("waybill_prebookings", "outbound_date"):
        op.add_column("waybill_prebookings", sa.Column("outbound_date", sa.Date(), nullable=True))


def downgrade() -> None:
    if _has_column("waybill_prebookings", "outbound_date"):
        op.drop_column("waybill_prebookings", "outbound_date")
    if _has_column("air_waybills", "outbound_date"):
        op.drop_column("air_waybills", "outbound_date")
