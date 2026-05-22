"""add general cargo flag to boxes

Revision ID: 20260522_0017
Revises: 20260522_0016
Create Date: 2026-05-22 18:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260522_0017"
down_revision: Union[str, None] = "20260522_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("boxes", "is_general_cargo"):
        op.add_column(
            "boxes",
            sa.Column("is_general_cargo", sa.Boolean(), server_default=sa.false(), nullable=False),
        )


def downgrade() -> None:
    if _has_column("boxes", "is_general_cargo"):
        op.drop_column("boxes", "is_general_cargo")
