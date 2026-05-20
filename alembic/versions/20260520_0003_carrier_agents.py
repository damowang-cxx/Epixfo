"""carrier agents

Revision ID: 20260520_0003
Revises: 20260519_0002
Create Date: 2026-05-20 03:30:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260520_0003"
down_revision: Union[str, None] = "20260519_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "carrier_agents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("carrier_code", sa.String(length=16), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("contact_person", sa.String(length=128), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carrier_code"], ["carriers.carrier_code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_code", "agent_name", name="uq_carrier_agent_name"),
    )
    op.create_index("idx_carrier_agents_carrier_code", "carrier_agents", ["carrier_code"])

    op.add_column("air_waybills", sa.Column("carrier_agent_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_air_waybills_carrier_agent_id",
        "air_waybills",
        "carrier_agents",
        ["carrier_agent_id"],
        ["id"],
    )
    op.create_index("idx_air_waybills_carrier_agent_id", "air_waybills", ["carrier_agent_id"])


def downgrade() -> None:
    op.drop_index("idx_air_waybills_carrier_agent_id", table_name="air_waybills")
    op.drop_constraint("fk_air_waybills_carrier_agent_id", "air_waybills", type_="foreignkey")
    op.drop_column("air_waybills", "carrier_agent_id")
    op.drop_index("idx_carrier_agents_carrier_code", table_name="carrier_agents")
    op.drop_table("carrier_agents")
