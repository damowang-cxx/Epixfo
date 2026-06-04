"""add warehouse planning drafts

Revision ID: 20260604_0030
Revises: 20260528_0029
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260604_0030"
down_revision: Union[str, None] = "20260528_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("warehouse_planning_drafts"):
        return
    op.create_table(
        "warehouse_planning_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("rows", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_warehouse_planning_draft_user"),
    )
    op.create_index("idx_warehouse_planning_drafts_user_id", "warehouse_planning_drafts", ["user_id"])


def downgrade() -> None:
    if not _has_table("warehouse_planning_drafts"):
        return
    op.drop_index("idx_warehouse_planning_drafts_user_id", table_name="warehouse_planning_drafts")
    op.drop_table("warehouse_planning_drafts")
