"""add consignees + consignee_contacts and air_waybills.consignee_contact_id

Revision ID: 20260521_0012
Revises: 20260521_0011
Create Date: 2026-05-21 06:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0012"
down_revision: Union[str, None] = "20260521_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consignees",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_consignees_name"),
    )

    op.create_table(
        "consignee_contacts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("consignee_id", sa.BigInteger(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("tax_info", sa.Text(), nullable=True),
        sa.Column("notify_info", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["consignee_id"], ["consignees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_consignee_contacts_consignee_id", "consignee_contacts", ["consignee_id"])

    op.add_column("air_waybills", sa.Column("consignee_contact_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_air_waybills_consignee_contact_id",
        "air_waybills",
        "consignee_contacts",
        ["consignee_contact_id"],
        ["id"],
    )
    op.create_index("idx_air_waybills_consignee_contact_id", "air_waybills", ["consignee_contact_id"])


def downgrade() -> None:
    op.drop_index("idx_air_waybills_consignee_contact_id", table_name="air_waybills")
    op.drop_constraint("fk_air_waybills_consignee_contact_id", "air_waybills", type_="foreignkey")
    op.drop_column("air_waybills", "consignee_contact_id")
    op.drop_index("idx_consignee_contacts_consignee_id", table_name="consignee_contacts")
    op.drop_table("consignee_contacts")
    op.drop_table("consignees")
