"""add consignee contact name and structured notify party

Revision ID: 20260521_0013
Revises: 20260521_0012
Create Date: 2026-05-21 07:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0013"
down_revision: Union[str, None] = "20260521_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("consignee_contacts", sa.Column("name", sa.String(length=128), nullable=True))
    op.execute(
        """
        UPDATE consignee_contacts AS cc
        SET name = LEFT(COALESCE(NULLIF(BTRIM(c.name), ''), 'Consignee'), 128)
        FROM consignees AS c
        WHERE cc.consignee_id = c.id
          AND (cc.name IS NULL OR BTRIM(cc.name) = '')
        """
    )
    op.execute(
        """
        UPDATE consignee_contacts
        SET name = 'Consignee'
        WHERE name IS NULL OR BTRIM(name) = ''
        """
    )
    op.alter_column("consignee_contacts", "name", existing_type=sa.String(length=128), nullable=False)

    op.create_table(
        "consignee_notify_parties",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("consignee_contact_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("tax_info", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["consignee_contact_id"], ["consignee_contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consignee_contact_id", name="uq_consignee_notify_parties_contact_id"),
    )
    op.create_index(
        "idx_consignee_notify_parties_contact_id",
        "consignee_notify_parties",
        ["consignee_contact_id"],
    )
    op.execute(
        """
        INSERT INTO consignee_notify_parties (
            consignee_contact_id,
            name,
            remark,
            enabled
        )
        SELECT
            id,
            LEFT(
                COALESCE(
                    NULLIF(BTRIM(SPLIT_PART(REPLACE(notify_info, E'\r\n', E'\n'), E'\n', 1)), ''),
                    'Notify Party'
                ),
                128
            ),
            notify_info,
            enabled
        FROM consignee_contacts
        WHERE notify_info IS NOT NULL
          AND BTRIM(notify_info) <> ''
        """
    )


def downgrade() -> None:
    op.drop_index("idx_consignee_notify_parties_contact_id", table_name="consignee_notify_parties")
    op.drop_table("consignee_notify_parties")
    op.drop_column("consignee_contacts", "name")
