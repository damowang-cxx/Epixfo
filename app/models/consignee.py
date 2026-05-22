from __future__ import annotations

from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Consignee(Base, TimestampMixin):
    """收件厂商（顶层组织）。一个厂商可下属多条 ConsigneeContact 记录。"""

    __tablename__ = "consignees"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    remark: Mapped[Optional[str]] = mapped_column(Text)

    contacts: Mapped[list[ConsigneeContact]] = relationship(
        back_populates="consignee",
        cascade="all, delete-orphan",
    )


class ConsigneeContact(Base, TimestampMixin):
    """收件人记录（厂商下的某地点 / 某入境口岸具体信息）。

    半结构化设计：核心字段独立（地址 / 邮箱 / 电话），税号与通知人信息用自由文本，
    便于兼容不同国家差异化的号码格式。
    """

    __tablename__ = "consignee_contacts"
    __table_args__ = (
        Index("idx_consignee_contacts_consignee_id", "consignee_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    consignee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("consignees.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    tax_info: Mapped[Optional[str]] = mapped_column(Text)
    notify_info: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    consignee: Mapped[Consignee] = relationship(back_populates="contacts")
    notify_party: Mapped[Optional[ConsigneeNotifyParty]] = relationship(
        back_populates="consignee_contact",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ConsigneeNotifyParty(Base, TimestampMixin):
    """Structured notify party data bound one-to-one to a consignee contact."""

    __tablename__ = "consignee_notify_parties"
    __table_args__ = (
        UniqueConstraint("consignee_contact_id", name="uq_consignee_notify_parties_contact_id"),
        Index("idx_consignee_notify_parties_contact_id", "consignee_contact_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    consignee_contact_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("consignee_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    tax_info: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    consignee_contact: Mapped[ConsigneeContact] = relationship(back_populates="notify_party")
