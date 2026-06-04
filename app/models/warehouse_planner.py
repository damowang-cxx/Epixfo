from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class WarehousePlanningDraft(Base, TimestampMixin):
    __tablename__ = "warehouse_planning_drafts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_warehouse_planning_draft_user"),
        Index("idx_warehouse_planning_drafts_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rows: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    user = relationship("User")
