"""add carrier query adapter metadata and pool ordering

Revision ID: 20260610_0033
Revises: 20260609_0032
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260610_0033"
down_revision: Union[str, None] = "20260609_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


carrier_query_method = postgresql.ENUM(
    "protocol",
    "playwright",
    "hybrid",
    name="carrier_query_method",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "carrier_query_adapters",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("adapter_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("adapter_type", sa.String(length=16), server_default="dedicated", nullable=False),
        sa.Column("query_method", carrier_query_method, nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("adapter_type in ('dedicated', 'general')", name="ck_carrier_query_adapters_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adapter_code", name="uq_carrier_query_adapters_code"),
    )
    op.create_index(
        "idx_carrier_query_adapters_type_order",
        "carrier_query_adapters",
        ["adapter_type", "display_order"],
        unique=False,
    )

    adapters_table = sa.table(
        "carrier_query_adapters",
        sa.column("adapter_code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("adapter_type", sa.String),
        sa.column("query_method", carrier_query_method),
        sa.column("enabled", sa.Boolean),
        sa.column("display_order", sa.Integer),
        sa.column("remark", sa.Text),
    )
    op.bulk_insert(
        adapters_table,
        [
            {
                "adapter_code": "cz_adapter",
                "display_name": "南航 CZ 查询",
                "adapter_type": "dedicated",
                "query_method": "hybrid",
                "enabled": True,
                "display_order": 10,
                "remark": "南航专属查询适配器",
            },
            {
                "adapter_code": "ek_adapter",
                "display_name": "阿联酋航空 EK 查询",
                "adapter_type": "dedicated",
                "query_method": "protocol",
                "enabled": True,
                "display_order": 20,
                "remark": "阿联酋航空专属查询适配器",
            },
            {
                "adapter_code": "general_adapter",
                "display_name": "51tracking 通用查询",
                "adapter_type": "general",
                "query_method": "protocol",
                "enabled": True,
                "display_order": 1,
                "remark": "通用航司查询适配器",
            },
        ],
    )

    op.add_column("waybill_query_snapshots", sa.Column("adapter_type", sa.String(length=16), nullable=True))
    op.execute(
        """
        UPDATE waybill_query_snapshots
        SET adapter_type = CASE
            WHEN adapter_code = 'general_adapter' THEN 'general'
            WHEN adapter_code IN ('cz_adapter', 'ek_adapter') THEN 'dedicated'
            ELSE NULL
        END
        """
    )


def downgrade() -> None:
    op.drop_column("waybill_query_snapshots", "adapter_type")
    op.drop_index("idx_carrier_query_adapters_type_order", table_name="carrier_query_adapters")
    op.drop_table("carrier_query_adapters")
