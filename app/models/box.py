from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin


class BoxDocument(Base, CreatedAtMixin):
    __tablename__ = "box_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    file_hash: Mapped[Optional[str]] = mapped_column(String(128))
    bound_waybill_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("air_waybills.id"))
    uploaded_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    boxes: Mapped[list[Box]] = relationship(back_populates="document")
    receipts: Mapped[list[WarehouseReceipt]] = relationship(back_populates="source_document")


class WarehouseReceipt(Base, TimestampMixin):
    __tablename__ = "warehouse_receipts"
    __table_args__ = (
        Index("idx_warehouse_receipts_waybill_id", "waybill_id"),
        Index("idx_warehouse_receipts_prebooking_id", "prebooking_id"),
        Index("idx_warehouse_receipts_warehouse_no", "warehouse_no"),
        Index("idx_warehouse_receipts_display_order", "display_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_no: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    waybill_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("air_waybills.id", ondelete="SET NULL"))
    prebooking_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("waybill_prebookings.id", ondelete="SET NULL"))
    source_document_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("box_documents.id", ondelete="SET NULL"))
    uploaded_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    total_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    weight_volume_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    channel_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    display_order: Mapped[Optional[int]] = mapped_column(Integer)

    source_document: Mapped[Optional[BoxDocument]] = relationship(back_populates="receipts")
    prebooking = relationship("WaybillPrebooking", back_populates="receipts")
    boxes: Mapped[list[Box]] = relationship(back_populates="warehouse_receipt")

    @property
    def uploaded_at(self) -> datetime:
        if self.source_document and self.source_document.uploaded_at:
            return self.source_document.uploaded_at
        return self.created_at


class Box(Base, TimestampMixin):
    __tablename__ = "boxes"
    __table_args__ = (
        Index("idx_boxes_current_waybill_id", "current_waybill_id"),
        Index("idx_boxes_document_id", "document_id"),
        Index("idx_boxes_warehouse_receipt_id", "warehouse_receipt_id"),
        UniqueConstraint("box_no", name="uq_boxes_box_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_no: Mapped[str] = mapped_column(String(128), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("box_documents.id", ondelete="SET NULL"))
    warehouse_receipt_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("warehouse_receipts.id", ondelete="SET NULL"),
    )
    current_waybill_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("air_waybills.id", ondelete="SET NULL"))
    warehouse_waybill_no: Mapped[Optional[str]] = mapped_column(String(128))
    goods_name: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    original_volume_info: Mapped[Optional[str]] = mapped_column(Text)
    original_weight_volume_ratio: Mapped[Optional[str]] = mapped_column(String(128))
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    weight_volume_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    source_row_number: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="reserved", server_default="reserved")
    is_general_cargo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    never_bound_direct_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    unbound_reason: Mapped[Optional[str]] = mapped_column(String(32))
    unbound_remark: Mapped[Optional[str]] = mapped_column(Text)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    document: Mapped[Optional[BoxDocument]] = relationship(back_populates="boxes")
    warehouse_receipt: Mapped[Optional[WarehouseReceipt]] = relationship(back_populates="boxes")
    items: Mapped[list[BoxItem]] = relationship(back_populates="box", cascade="all, delete-orphan")

    @property
    def box_conflict(self) -> Optional[dict]:
        if not isinstance(self.raw_data, dict):
            return None
        conflict = self.raw_data.get("box_conflict")
        return conflict if isinstance(conflict, dict) else None


class BoxItem(Base, TimestampMixin):
    __tablename__ = "box_items"
    __table_args__ = (
        Index("idx_box_items_box_id", "box_id"),
        Index("idx_box_items_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("boxes.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("box_documents.id", ondelete="SET NULL"))
    warehouse_waybill_no: Mapped[Optional[str]] = mapped_column(String(128))
    goods_name: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    source_row_number: Mapped[Optional[int]] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    box: Mapped[Box] = relationship(back_populates="items")
