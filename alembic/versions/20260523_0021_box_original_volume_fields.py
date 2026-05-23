"""add original warehouse volume fields

Revision ID: 20260523_0021
Revises: 20260523_0020
Create Date: 2026-05-23 17:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260523_0021"
down_revision: Union[str, None] = "20260523_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("boxes", "original_volume_info"):
        op.add_column("boxes", sa.Column("original_volume_info", sa.Text(), nullable=True))
    if not _has_column("boxes", "original_weight_volume_ratio"):
        op.add_column("boxes", sa.Column("original_weight_volume_ratio", sa.String(length=128), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE boxes
            SET
                original_volume_info = COALESCE(
                    original_volume_info,
                    NULLIF(raw_data ->> '收货体积信息', ''),
                    NULLIF(raw_data ->> '体积', ''),
                    NULLIF(raw_data ->> '方数', ''),
                    NULLIF(raw_data ->> 'volume', ''),
                    NULLIF(raw_data ->> 'volume cbm', '')
                ),
                original_weight_volume_ratio = COALESCE(
                    original_weight_volume_ratio,
                    NULLIF(raw_data ->> '收货重量/方', ''),
                    NULLIF(raw_data ->> '重量/方', ''),
                    NULLIF(raw_data ->> 'weight/volume', ''),
                    NULLIF(raw_data ->> 'weight volume ratio', '')
                )
            WHERE raw_data IS NOT NULL
              AND (
                original_volume_info IS NULL
                OR original_weight_volume_ratio IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    if _has_column("boxes", "original_weight_volume_ratio"):
        op.drop_column("boxes", "original_weight_volume_ratio")
    if _has_column("boxes", "original_volume_info"):
        op.drop_column("boxes", "original_volume_info")
