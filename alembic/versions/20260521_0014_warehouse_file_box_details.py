"""add warehouse file box detail fields

Revision ID: 20260521_0014
Revises: 20260521_0013
Create Date: 2026-05-21 08:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0014"
down_revision: Union[str, None] = "20260521_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("boxes", sa.Column("warehouse_waybill_no", sa.String(length=128), nullable=True))
    op.add_column("boxes", sa.Column("goods_name", sa.Text(), nullable=True))
    op.add_column("boxes", sa.Column("quantity", sa.Integer(), nullable=True))
    op.add_column("boxes", sa.Column("weight", sa.Numeric(12, 3), nullable=True))
    op.add_column("boxes", sa.Column("volume", sa.Numeric(12, 3), nullable=True))
    op.add_column("boxes", sa.Column("weight_volume_ratio", sa.Numeric(12, 3), nullable=True))
    op.add_column("boxes", sa.Column("source_row_number", sa.Integer(), nullable=True))
    op.create_index("idx_boxes_current_waybill_id", "boxes", ["current_waybill_id"])
    op.create_index("idx_boxes_document_id", "boxes", ["document_id"])


def downgrade() -> None:
    op.drop_index("idx_boxes_document_id", table_name="boxes")
    op.drop_index("idx_boxes_current_waybill_id", table_name="boxes")
    op.drop_column("boxes", "source_row_number")
    op.drop_column("boxes", "weight_volume_ratio")
    op.drop_column("boxes", "volume")
    op.drop_column("boxes", "weight")
    op.drop_column("boxes", "quantity")
    op.drop_column("boxes", "goods_name")
    op.drop_column("boxes", "warehouse_waybill_no")
