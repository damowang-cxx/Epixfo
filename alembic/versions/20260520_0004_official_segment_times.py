"""add precise times to official flight segments

Revision ID: 20260520_0004
Revises: 20260520_0003
Create Date: 2026-05-20 04:30:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260520_0004"
down_revision: Union[str, None] = "20260520_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "waybill_official_flight_segments",
        sa.Column("departure_planned_time", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "waybill_official_flight_segments",
        sa.Column("departure_actual_time", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "waybill_official_flight_segments",
        sa.Column("arrival_planned_time", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "waybill_official_flight_segments",
        sa.Column("arrival_actual_time", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("waybill_official_flight_segments", "arrival_actual_time")
    op.drop_column("waybill_official_flight_segments", "arrival_planned_time")
    op.drop_column("waybill_official_flight_segments", "departure_actual_time")
    op.drop_column("waybill_official_flight_segments", "departure_planned_time")
