"""add user table preferences

Revision ID: 20260528_0028
Revises: 20260527_0027
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_0028"
down_revision: Union[str, None] = "20260527_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("user_table_preferences"):
        return
    op.create_table(
        "user_table_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("table_key", sa.String(length=128), nullable=False),
        sa.Column("column_order", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "table_key", name="uq_user_table_preference"),
    )
    op.create_index("idx_user_table_preferences_user_id", "user_table_preferences", ["user_id"])


def downgrade() -> None:
    if not _has_table("user_table_preferences"):
        return
    op.drop_index("idx_user_table_preferences_user_id", table_name="user_table_preferences")
    op.drop_table("user_table_preferences")
