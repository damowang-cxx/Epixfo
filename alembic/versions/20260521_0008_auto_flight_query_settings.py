"""add auto flight query settings

Revision ID: 20260521_0008
Revises: 20260521_0007
Create Date: 2026-05-21 02:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0008"
down_revision: Union[str, None] = "20260521_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auto_flight_query_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("fallback_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("fallback_adapter_code", sa.String(length=64), server_default="general_adapter", nullable=False),
        sa.Column("query_interval_hours", sa.Integer(), server_default="2", nullable=False),
        sa.Column("scan_limit", sa.Integer(), server_default="50", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO auto_flight_query_settings (
            id,
            fallback_enabled,
            fallback_adapter_code,
            query_interval_hours,
            scan_limit
        )
        VALUES (1, true, 'general_adapter', 2, 50)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("auto_flight_query_settings")
