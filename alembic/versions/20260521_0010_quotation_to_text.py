"""convert air_waybills.quotation from numeric to varchar

Revision ID: 20260521_0010
Revises: 20260521_0009
Create Date: 2026-05-21 04:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0010"
down_revision: Union[str, None] = "20260521_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """报价改为自由文本（允许"面议"/"USD 5/kg"等非数字描述）。"""
    op.alter_column(
        "air_waybills",
        "quotation",
        existing_type=sa.Numeric(12, 2),
        type_=sa.String(length=64),
        existing_nullable=True,
        postgresql_using="quotation::text",
    )


def downgrade() -> None:
    """回退到 Numeric；非数字内容会被强转失败 -> 先清空。"""
    op.execute("UPDATE air_waybills SET quotation = NULL WHERE quotation !~ '^-?[0-9]+(\\.[0-9]+)?$'")
    op.alter_column(
        "air_waybills",
        "quotation",
        existing_type=sa.String(length=64),
        type_=sa.Numeric(12, 2),
        existing_nullable=True,
        postgresql_using="NULLIF(quotation, '')::numeric(12,2)",
    )
