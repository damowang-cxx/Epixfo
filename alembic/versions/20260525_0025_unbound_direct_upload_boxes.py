"""mark boxes uploaded directly to unbound pool

Revision ID: 20260525_0025
Revises: 20260525_0024
Create Date: 2026-05-25 20:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0025"
down_revision: Union[str, None] = "20260525_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("boxes", "never_bound_direct_upload"):
        op.add_column(
            "boxes",
            sa.Column(
                "never_bound_direct_upload",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    if _has_column("boxes", "never_bound_direct_upload"):
        op.drop_column("boxes", "never_bound_direct_upload")
