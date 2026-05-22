"""add waybill boards

Revision ID: 20260522_0018
Revises: 20260522_0017
Create Date: 2026-05-22 19:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260522_0018"
down_revision: Union[str, None] = "20260522_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "waybill_boards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("board_no", sa.String(length=16), nullable=False),
        sa.Column("actual_board_no", sa.String(length=128), nullable=True),
        sa.Column("consignee_contact_id", sa.BigInteger(), nullable=True),
        sa.Column("consignee_text", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["consignee_contact_id"], ["consignee_contacts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_no", name="uq_waybill_boards_board_no"),
    )
    op.create_index("idx_waybill_boards_board_no", "waybill_boards", ["board_no"])
    op.create_index("idx_waybill_boards_consignee_contact_id", "waybill_boards", ["consignee_contact_id"])

    op.add_column("air_waybills", sa.Column("board_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_air_waybills_board_id",
        "air_waybills",
        "waybill_boards",
        ["board_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_air_waybills_board_id", "air_waybills", ["board_id"])


def downgrade() -> None:
    op.drop_index("idx_air_waybills_board_id", table_name="air_waybills")
    op.drop_constraint("fk_air_waybills_board_id", "air_waybills", type_="foreignkey")
    op.drop_column("air_waybills", "board_id")
    op.drop_index("idx_waybill_boards_consignee_contact_id", table_name="waybill_boards")
    op.drop_index("idx_waybill_boards_board_no", table_name="waybill_boards")
    op.drop_table("waybill_boards")
