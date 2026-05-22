"""remove closed lifecycle status

Revision ID: 20260522_0015
Revises: 20260521_0014
Create Date: 2026-05-22 14:00:00.000000

"""
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op


revision: str = "20260522_0015"
down_revision: Union[str, None] = "20260521_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_VALUES = (
    "created",
    "waiting_monitor",
    "monitoring",
    "warehouse_received",
    "loaded",
    "departed",
    "arrived",
    "pickup_notified",
    "picked_up",
    "voided",
)

OLD_VALUES = (
    "created",
    "waiting_monitor",
    "monitoring",
    "warehouse_received",
    "loaded",
    "departed",
    "arrived",
    "pickup_notified",
    "picked_up",
    "closed",
    "voided",
)


def _create_enum(values: tuple[str, ...]) -> None:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    op.execute(f"CREATE TYPE waybill_lifecycle_status AS ENUM ({quoted_values})")


def _replace_enum(values: tuple[str, ...]) -> None:
    op.execute("ALTER TYPE waybill_lifecycle_status RENAME TO waybill_lifecycle_status_old")
    _create_enum(values)
    op.execute("ALTER TABLE air_waybills ALTER COLUMN lifecycle_status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE air_waybills
        ALTER COLUMN lifecycle_status TYPE waybill_lifecycle_status
        USING lifecycle_status::text::waybill_lifecycle_status
        """
    )
    op.execute("ALTER TABLE air_waybills ALTER COLUMN lifecycle_status SET DEFAULT 'created'")
    op.execute("DROP TYPE waybill_lifecycle_status_old")


def upgrade() -> None:
    op.execute("UPDATE air_waybills SET lifecycle_status = 'picked_up' WHERE lifecycle_status = 'closed'")
    _replace_enum(NEW_VALUES)


def downgrade() -> None:
    _replace_enum(OLD_VALUES)
