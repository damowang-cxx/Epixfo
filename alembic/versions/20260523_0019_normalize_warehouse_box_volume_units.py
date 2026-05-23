"""normalize warehouse box volume units

Revision ID: 20260523_0019
Revises: 20260522_0018
Create Date: 2026-05-23 10:00:00.000000

"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa


revision: str = "20260523_0019"
down_revision: Union[str, None] = "20260522_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DECIMAL_001 = Decimal("0.001")
DIMENSION_VOLUME_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\*|x|X|×)\s*(\d+(?:\.\d+)?)\s*(?:\*|x|X|×)\s*(\d+(?:\.\d+)?)"
)
VOLUME_KEYS = ("收货体积信息", "体积", "方数", "volume", "volume cbm")


def upgrade() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, weight, volume, weight_volume_ratio, raw_data
                FROM boxes
                WHERE raw_data IS NOT NULL
                """
            )
        ).mappings()
    )

    for row in rows:
        raw_data = _as_dict(row["raw_data"])
        source_value = _find_dimension_source(raw_data)
        if source_value is None:
            continue

        next_volume = _dimension_to_cbm(source_value)
        if next_volume is None:
            continue

        previous_volume = _to_decimal(row["volume"])
        if previous_volume == next_volume:
            continue

        weight = _to_decimal(row["weight"])
        next_ratio = _ratio(weight, next_volume)
        raw_data["volume_unit_normalization"] = {
            "source": "dimension_to_cbm",
            "raw_value": str(source_value),
            "old_volume": str(previous_volume),
            "new_volume": str(next_volume),
            "unit": "CBM",
        }

        bind.execute(
            sa.text(
                """
                UPDATE boxes
                SET
                    volume = :volume,
                    weight_volume_ratio = :ratio,
                    raw_data = CAST(:raw_data AS JSONB),
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "volume": next_volume,
                "ratio": next_ratio,
                "raw_data": json.dumps(raw_data, ensure_ascii=False, default=str),
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE warehouse_receipts wr
            SET
                total_quantity = COALESCE(summary.total_quantity, 0),
                total_weight = COALESCE(summary.total_weight, 0),
                total_volume = COALESCE(summary.total_volume, 0),
                weight_volume_ratio = CASE
                    WHEN COALESCE(summary.total_volume, 0) > 0
                        THEN ROUND((COALESCE(summary.total_weight, 0) / summary.total_volume)::numeric, 3)
                    ELSE 0
                END,
                updated_at = now()
            FROM (
                SELECT
                    warehouse_receipt_id,
                    SUM(COALESCE(quantity, 0)) AS total_quantity,
                    ROUND(SUM(COALESCE(weight, 0))::numeric, 3) AS total_weight,
                    ROUND(SUM(COALESCE(volume, 0))::numeric, 3) AS total_volume
                FROM boxes
                WHERE warehouse_receipt_id IS NOT NULL
                GROUP BY warehouse_receipt_id
            ) summary
            WHERE wr.id = summary.warehouse_receipt_id
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE warehouse_receipts wr
            SET
                total_quantity = 0,
                total_weight = 0,
                total_volume = 0,
                weight_volume_ratio = 0,
                updated_at = now()
            WHERE NOT EXISTS (
                SELECT 1
                FROM boxes b
                WHERE b.warehouse_receipt_id = wr.id
            )
            """
        )
    )


def downgrade() -> None:
    # Data normalization is intentionally not reversed.
    pass


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _find_dimension_source(raw_data: dict[str, Any]) -> Any | None:
    for key in VOLUME_KEYS:
        value = raw_data.get(key)
        if value is not None and DIMENSION_VOLUME_PATTERN.search(str(value)):
            return value
    for value in raw_data.values():
        if value is not None and DIMENSION_VOLUME_PATTERN.search(str(value)):
            return value
    return None


def _dimension_to_cbm(value: Any) -> Decimal | None:
    match = DIMENSION_VOLUME_PATTERN.search(str(value))
    if not match:
        return None
    try:
        length, width, height = (Decimal(part) for part in match.groups())
    except (InvalidOperation, ValueError):
        return None
    if length <= 0 or width <= 0 or height <= 0:
        return None
    return (length * width * height / Decimal("1000000")).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)


def _to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.000")
    try:
        return Decimal(str(value)).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.000")


def _ratio(weight: Decimal, volume: Decimal) -> Decimal:
    if volume <= 0:
        return Decimal("0.000")
    return (weight / volume).quantize(DECIMAL_001, rounding=ROUND_HALF_UP)
