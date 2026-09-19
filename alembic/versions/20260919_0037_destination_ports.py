"""Destination port registry and manual receipt destination ownership."""
from app.core.platform_patch import patch_platform_wmi
patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260919_0037"
down_revision = "20260919_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("destination_ports", sa.Column("code", sa.String(16), primary_key=True))
    op.execute("INSERT INTO destination_ports (code) VALUES ('AMS'), ('LHR')")
    # Keep existing destinations selectable, including automatic multi-port tags.
    op.execute("""
        INSERT INTO destination_ports (code)
        SELECT DISTINCT upper(trim(code)) FROM (
            SELECT destination_port AS code FROM air_waybills
            UNION SELECT destination_port FROM waybill_prebookings
            UNION SELECT jsonb_array_elements_text(channel_tags) FROM warehouse_receipts
        ) existing
        WHERE code IS NOT NULL AND upper(trim(code)) ~ '^[A-Z0-9]{3,16}$'
        ON CONFLICT DO NOTHING
    """)
    op.add_column("warehouse_receipts", sa.Column("destination_ports_override", postgresql.JSONB(none_as_null=True), nullable=True))


def downgrade() -> None:
    op.drop_column("warehouse_receipts", "destination_ports_override")
    op.drop_table("destination_ports")
