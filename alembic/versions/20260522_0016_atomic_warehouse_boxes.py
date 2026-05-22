"""atomic warehouse box bindings

Revision ID: 20260522_0016
Revises: 20260522_0015
Create Date: 2026-05-22 16:00:00.000000

"""
import json
from decimal import Decimal
from typing import Sequence, Union

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260522_0016"
down_revision: Union[str, None] = "20260522_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_decimal(value):
    if value is None:
        return Decimal("0.000")
    return Decimal(str(value)).quantize(Decimal("0.001"))


def _ratio(weight: Decimal, volume: Decimal) -> Decimal:
    if volume <= 0:
        return Decimal("0.000")
    return (weight / volume).quantize(Decimal("0.001"))


def _jsonb(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def upgrade() -> None:
    op.create_table(
        "warehouse_receipts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("warehouse_no", sa.String(length=128), nullable=False),
        sa.Column("waybill_id", sa.BigInteger(), nullable=True),
        sa.Column("source_document_id", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column("total_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("total_volume", sa.Numeric(12, 3), nullable=True),
        sa.Column("weight_volume_ratio", sa.Numeric(12, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["box_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["waybill_id"], ["air_waybills.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_no", name="uq_warehouse_receipts_warehouse_no"),
    )
    op.create_index("idx_warehouse_receipts_waybill_id", "warehouse_receipts", ["waybill_id"])
    op.create_index("idx_warehouse_receipts_warehouse_no", "warehouse_receipts", ["warehouse_no"])

    op.add_column("boxes", sa.Column("warehouse_receipt_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_boxes_warehouse_receipt_id",
        "boxes",
        "warehouse_receipts",
        ["warehouse_receipt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_boxes_warehouse_receipt_id", "boxes", ["warehouse_receipt_id"])

    op.create_table(
        "box_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("box_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=True),
        sa.Column("warehouse_waybill_no", sa.String(length=128), nullable=True),
        sa.Column("goods_name", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 3), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["box_id"], ["boxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["box_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_box_items_box_id", "box_items", ["box_id"])
    op.create_index("idx_box_items_document_id", "box_items", ["document_id"])

    bind = op.get_bind()
    waybill_rows = bind.execute(
        sa.text(
            """
            SELECT id, warehouse_no
            FROM air_waybills
            WHERE warehouse_no IS NOT NULL AND warehouse_no <> ''
            """
        )
    ).mappings()
    for row in waybill_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO warehouse_receipts (warehouse_no, waybill_id)
                VALUES (:warehouse_no, :waybill_id)
                ON CONFLICT (warehouse_no) DO UPDATE
                SET waybill_id = EXCLUDED.waybill_id, updated_at = now()
                """
            ),
            {"warehouse_no": row["warehouse_no"], "waybill_id": row["id"]},
        )

    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT
                    b.id,
                    b.box_no,
                    b.document_id,
                    b.current_waybill_id,
                    b.warehouse_waybill_no,
                    b.goods_name,
                    b.quantity,
                    b.weight,
                    b.volume,
                    b.weight_volume_ratio,
                    b.source_row_number,
                    b.status,
                    b.raw_data,
                    wr.id AS receipt_id
                FROM boxes b
                LEFT JOIN air_waybills awb ON awb.id = b.current_waybill_id
                LEFT JOIN warehouse_receipts wr ON wr.warehouse_no = awb.warehouse_no
                ORDER BY b.box_no, b.id
                """
            )
        ).mappings()
    )

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["box_no"], []).append(dict(row))

    for box_no, group in grouped.items():
        primary = group[0]
        primary_id = primary["id"]
        receipt_ids = {item["receipt_id"] for item in group if item["receipt_id"] is not None}
        receipt_id = next(iter(receipt_ids)) if len(receipt_ids) == 1 else None
        current_waybill_ids = {item["current_waybill_id"] for item in group if item["current_waybill_id"] is not None}
        current_waybill_id = next(iter(current_waybill_ids)) if receipt_id is not None and len(current_waybill_ids) == 1 else None

        total_quantity = sum(int(item["quantity"] or 0) for item in group)
        total_weight = sum((_to_decimal(item["weight"]) for item in group), Decimal("0.000"))
        first_volume = next((_to_decimal(item["volume"]) for item in group if _to_decimal(item["volume"]) > 0), Decimal("0.000"))
        source_row_number = min([item["source_row_number"] for item in group if item["source_row_number"] is not None] or [None])
        raw_data = dict(primary["raw_data"] or {})
        if len(receipt_ids) > 1:
            raw_data["migration_unbound_reason"] = "duplicate_box_no_across_receipts"
            raw_data["migration_source_waybill_ids"] = sorted(current_waybill_ids)

        bind.execute(
            sa.text(
                """
                UPDATE boxes
                SET
                    warehouse_receipt_id = :receipt_id,
                    current_waybill_id = :current_waybill_id,
                    warehouse_waybill_no = :warehouse_waybill_no,
                    goods_name = :goods_name,
                    quantity = :quantity,
                    weight = :weight,
                    volume = :volume,
                    weight_volume_ratio = :ratio,
                    source_row_number = :source_row_number,
                    status = :status,
                    raw_data = CAST(:raw_data AS JSONB),
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "receipt_id": receipt_id,
                "current_waybill_id": current_waybill_id,
                "warehouse_waybill_no": primary["warehouse_waybill_no"],
                "goods_name": primary["goods_name"],
                "quantity": total_quantity or None,
                "weight": total_weight,
                "volume": first_volume,
                "ratio": _ratio(total_weight, first_volume),
                "source_row_number": source_row_number,
                "status": "bound" if receipt_id else "unbound",
                "raw_data": _jsonb(raw_data),
                "id": primary_id,
            },
        )

        for item in group:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO box_items (
                        box_id,
                        document_id,
                        warehouse_waybill_no,
                        goods_name,
                        quantity,
                        weight,
                        source_row_number,
                        raw_data
                    )
                    VALUES (
                        :box_id,
                        :document_id,
                        :warehouse_waybill_no,
                        :goods_name,
                        :quantity,
                        :weight,
                        :source_row_number,
                        CAST(:raw_data AS JSONB)
                    )
                    """
                ),
                {
                    "box_id": primary_id,
                    "document_id": item["document_id"],
                    "warehouse_waybill_no": item["warehouse_waybill_no"],
                    "goods_name": item["goods_name"],
                    "quantity": item["quantity"],
                    "weight": item["weight"],
                    "source_row_number": item["source_row_number"],
                    "raw_data": _jsonb(item["raw_data"]),
                },
            )

        duplicate_ids = [item["id"] for item in group[1:]]
        if duplicate_ids:
            bind.execute(
                sa.text("DELETE FROM boxes WHERE id IN :ids").bindparams(sa.bindparam("ids", expanding=True)),
                {"ids": duplicate_ids},
            )

    bind.execute(
        sa.text(
            """
            UPDATE warehouse_receipts wr
            SET
                total_quantity = COALESCE(summary.total_quantity, 0),
                total_weight = summary.total_weight,
                total_volume = summary.total_volume,
                weight_volume_ratio = CASE
                    WHEN summary.total_volume > 0 THEN ROUND((summary.total_weight / summary.total_volume)::numeric, 3)
                    ELSE 0
                END,
                updated_at = now()
            FROM (
                SELECT
                    warehouse_receipt_id,
                    SUM(COALESCE(quantity, 0)) AS total_quantity,
                    SUM(COALESCE(weight, 0)) AS total_weight,
                    SUM(COALESCE(volume, 0)) AS total_volume
                FROM boxes
                WHERE warehouse_receipt_id IS NOT NULL
                GROUP BY warehouse_receipt_id
            ) summary
            WHERE wr.id = summary.warehouse_receipt_id
            """
        )
    )

    op.create_unique_constraint("uq_boxes_box_no", "boxes", ["box_no"])


def downgrade() -> None:
    op.drop_constraint("uq_boxes_box_no", "boxes", type_="unique")
    op.drop_index("idx_box_items_document_id", table_name="box_items")
    op.drop_index("idx_box_items_box_id", table_name="box_items")
    op.drop_table("box_items")
    op.drop_index("idx_boxes_warehouse_receipt_id", table_name="boxes")
    op.drop_constraint("fk_boxes_warehouse_receipt_id", "boxes", type_="foreignkey")
    op.drop_column("boxes", "warehouse_receipt_id")
    op.drop_index("idx_warehouse_receipts_warehouse_no", table_name="warehouse_receipts")
    op.drop_index("idx_warehouse_receipts_waybill_id", table_name="warehouse_receipts")
    op.drop_table("warehouse_receipts")
