"""remove carrier code from carrier agents

Revision ID: 20260609_0032
Revises: 20260604_0031
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0032"
down_revision: Union[str, None] = "20260604_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _has_unique(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _foreign_key_name_for_column(table_name: str, column_name: str) -> str | None:
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_foreign_keys(table_name):
        if column_name in constraint.get("constrained_columns", []):
            return constraint.get("name")
    return None


def upgrade() -> None:
    if _has_unique("carrier_agents", "uq_carrier_agent_name"):
        op.drop_constraint("uq_carrier_agent_name", "carrier_agents", type_="unique")
    if _has_index("carrier_agents", "idx_carrier_agents_carrier_code"):
        op.drop_index("idx_carrier_agents_carrier_code", table_name="carrier_agents")
    fk_name = _foreign_key_name_for_column("carrier_agents", "carrier_code")
    if fk_name:
        op.drop_constraint(fk_name, "carrier_agents", type_="foreignkey")
    if _has_column("carrier_agents", "carrier_code"):
        op.drop_column("carrier_agents", "carrier_code")


def downgrade() -> None:
    if not _has_column("carrier_agents", "carrier_code"):
        op.add_column("carrier_agents", sa.Column("carrier_code", sa.String(length=16), nullable=True))
    if _foreign_key_name_for_column("carrier_agents", "carrier_code") is None:
        op.create_foreign_key(
            "carrier_agents_carrier_code_fkey",
            "carrier_agents",
            "carriers",
            ["carrier_code"],
            ["carrier_code"],
        )
    if not _has_unique("carrier_agents", "uq_carrier_agent_name"):
        op.create_unique_constraint("uq_carrier_agent_name", "carrier_agents", ["carrier_code", "agent_name"])
    if not _has_index("carrier_agents", "idx_carrier_agents_carrier_code"):
        op.create_index("idx_carrier_agents_carrier_code", "carrier_agents", ["carrier_code"])
