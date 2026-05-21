"""add departure_port to air_waybills

Revision ID: 20260520_0005
Revises: 20260520_0004
Create Date: 2026-05-20 05:30:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260520_0005"
down_revision: Union[str, None] = "20260520_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "air_waybills",
        sa.Column("departure_port", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("air_waybills", "departure_port")
