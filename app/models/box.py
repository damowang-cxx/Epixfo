from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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


class Box(Base, TimestampMixin):
    __tablename__ = "boxes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    box_no: Mapped[str] = mapped_column(String(128), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("box_documents.id", ondelete="SET NULL"))
    current_waybill_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("air_waybills.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="reserved", server_default="reserved")
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
