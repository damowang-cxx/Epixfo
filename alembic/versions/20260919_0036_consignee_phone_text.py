"""Allow multiple phone numbers for consignee contacts and notify parties."""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260919_0036"
down_revision: Union[str, None] = "20260618_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("consignee_contacts", "consignee_notify_parties"):
        op.alter_column(table, "phone", existing_type=sa.String(64), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # Refuse a lossy downgrade if any saved phone list exceeds the old limit.
    for table in ("consignee_contacts", "consignee_notify_parties"):
        op.execute(sa.text(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table} WHERE length(phone) > 64) "
            "THEN RAISE EXCEPTION 'Phone lists exceed 64 characters; downgrade would lose data'; "
            "END IF; END $$"
        ))
    for table in ("consignee_contacts", "consignee_notify_parties"):
        op.alter_column(table, "phone", existing_type=sa.Text(), type_=sa.String(64), existing_nullable=True)
