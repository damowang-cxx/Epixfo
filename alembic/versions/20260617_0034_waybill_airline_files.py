"""add waybill airline file attachments

Revision ID: 20260617_0034
Revises: 20260610_0033
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260617_0034"
down_revision: Union[str, None] = "20260610_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "waybill_airline_files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("extracted_waybill_no", sa.String(length=64), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waybill_id", name="uq_waybill_airline_files_waybill_id"),
    )
    op.create_index("idx_waybill_airline_files_waybill_id", "waybill_airline_files", ["waybill_id"], unique=False)
    op.create_index("idx_waybill_airline_files_uploaded_by", "waybill_airline_files", ["uploaded_by"], unique=False)
    op.create_index("idx_waybill_airline_files_uploaded_at", "waybill_airline_files", ["uploaded_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_waybill_airline_files_uploaded_at", table_name="waybill_airline_files")
    op.drop_index("idx_waybill_airline_files_uploaded_by", table_name="waybill_airline_files")
    op.drop_index("idx_waybill_airline_files_waybill_id", table_name="waybill_airline_files")
    op.drop_table("waybill_airline_files")
