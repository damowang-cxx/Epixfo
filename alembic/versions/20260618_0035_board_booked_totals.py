"""add board booked totals

Revision ID: 20260618_0035
Revises: 20260617_0034
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0035"
down_revision: Union[str, None] = "20260617_0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("waybill_boards", sa.Column("booked_volume", sa.Numeric(12, 3), nullable=True))
    op.add_column("waybill_boards", sa.Column("booked_weight", sa.Numeric(12, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("waybill_boards", "booked_weight")
    op.drop_column("waybill_boards", "booked_volume")
