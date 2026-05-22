"""add other_charge to air_waybills

Revision ID: 20260521_0009
Revises: 20260521_0008
Create Date: 2026-05-21 03:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0009"
down_revision: Union[str, None] = "20260521_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "air_waybills",
        sa.Column("other_charge", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("air_waybills", "other_charge")
