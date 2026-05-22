"""add contact_emails to carrier_agents

Revision ID: 20260521_0011
Revises: 20260521_0010
Create Date: 2026-05-21 05:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0011"
down_revision: Union[str, None] = "20260521_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "carrier_agents",
        sa.Column("contact_emails", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("carrier_agents", "contact_emails")
