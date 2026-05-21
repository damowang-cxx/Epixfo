"""seed emirates skycargo carrier

Revision ID: 20260521_0006
Revises: 20260520_0005
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op


revision: str = "20260521_0006"
down_revision: Union[str, None] = "20260520_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO carriers (carrier_code, carrier_name, carrier_name_en, enabled)
        VALUES ('EK', '阿联酋航空', 'Emirates SkyCargo', true)
        ON CONFLICT (carrier_code) DO UPDATE SET
            carrier_name = EXCLUDED.carrier_name,
            carrier_name_en = EXCLUDED.carrier_name_en,
            enabled = EXCLUDED.enabled,
            updated_at = NOW()
        """
    )
    op.execute(
        """
        INSERT INTO carrier_prefix_mappings (prefix, carrier_code, adapter_code, query_method, enabled, remark)
        VALUES ('176', 'EK', 'ek_adapter', 'protocol', true, '阿联酋航空 Emirates SkyCargo 查询适配')
        ON CONFLICT (prefix) DO UPDATE SET
            carrier_code = EXCLUDED.carrier_code,
            adapter_code = EXCLUDED.adapter_code,
            query_method = EXCLUDED.query_method,
            enabled = EXCLUDED.enabled,
            remark = EXCLUDED.remark,
            updated_at = NOW()
        """
    )
    op.execute(
        """
        INSERT INTO carrier_query_configs (carrier_code, adapter_code, query_method, base_url, remark)
        VALUES (
            'EK',
            'ek_adapter',
            'protocol',
            'https://eskycargo.emirates.com',
            '阿联酋航空 Emirates SkyCargo 协议查询配置'
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
    op.execute("UPDATE air_waybills SET carrier_code = 'UNKNOWN' WHERE carrier_code = 'EK'")
    op.execute("DELETE FROM carrier_query_configs WHERE carrier_code = 'EK' AND adapter_code = 'ek_adapter'")
    op.execute("DELETE FROM carrier_prefix_mappings WHERE prefix = '176' AND adapter_code = 'ek_adapter'")
    op.execute("DELETE FROM carriers WHERE carrier_code = 'EK'")
