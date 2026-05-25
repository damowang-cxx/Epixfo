"""rename customs staff role display name

Revision ID: 20260525_0022
Revises: 20260523_0021
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0022"
down_revision: Union[str, None] = "20260523_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE roles
            SET name = '清关人员'
            WHERE code = 'customs_staff'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE roles
            SET name = '出口报关人员'
            WHERE code = 'customs_staff'
            """
        )
    )
