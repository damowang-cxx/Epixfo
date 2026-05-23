"""add unbound reason fields to boxes

Revision ID: 20260523_0020
Revises: 20260523_0019
Create Date: 2026-05-23 16:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260523_0020"
down_revision: Union[str, None] = "20260523_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("boxes", "unbound_reason"):
        op.add_column("boxes", sa.Column("unbound_reason", sa.String(length=32), nullable=True))
    if not _has_column("boxes", "unbound_remark"):
        op.add_column("boxes", sa.Column("unbound_remark", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("boxes", "unbound_remark"):
        op.drop_column("boxes", "unbound_remark")
    if _has_column("boxes", "unbound_reason"):
        op.drop_column("boxes", "unbound_reason")
