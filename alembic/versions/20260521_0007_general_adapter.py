"""seed general adapter query config

Revision ID: 20260521_0007
Revises: 20260521_0006
Create Date: 2026-05-21 01:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op


revision: str = "20260521_0007"
down_revision: Union[str, None] = "20260521_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO carrier_query_configs (carrier_code, adapter_code, query_method, base_url, remark)
        VALUES (
            'UNKNOWN',
            'general_adapter',
            'protocol',
            'https://www.51tracking.com',
            '51tracking 航空货运通用兜底查询适配'
        )
        ON CONFLICT (carrier_code, adapter_code) DO UPDATE SET
            query_method = EXCLUDED.query_method,
            base_url = EXCLUDED.base_url,
            remark = EXCLUDED.remark,
            enabled = true,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM carrier_query_configs WHERE carrier_code = 'UNKNOWN' AND adapter_code = 'general_adapter'")
