from __future__ import annotations

from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Enum, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CarrierAdapterType, CarrierQueryMethod, enum_values
from app.models.mixins import TimestampMixin


class Carrier(Base, TimestampMixin):
    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    carrier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    carrier_name_en: Mapped[Optional[str]] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    prefix_mappings: Mapped[list[CarrierPrefixMapping]] = relationship(back_populates="carrier")
    query_configs: Mapped[list[CarrierQueryConfig]] = relationship(back_populates="carrier")


class CarrierPrefixMapping(Base, TimestampMixin):
    __tablename__ = "carrier_prefix_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    carrier_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("carriers.carrier_code"),
        nullable=False,
    )
    adapter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    query_method: Mapped[CarrierQueryMethod] = mapped_column(
        Enum(CarrierQueryMethod, name="carrier_query_method", values_callable=enum_values),
        nullable=False,
        default=CarrierQueryMethod.HYBRID,
        server_default=CarrierQueryMethod.HYBRID.value,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    remark: Mapped[Optional[str]] = mapped_column(Text)

    carrier: Mapped[Carrier] = relationship(back_populates="prefix_mappings")


class CarrierQueryConfig(Base, TimestampMixin):
    __tablename__ = "carrier_query_configs"
    __table_args__ = (UniqueConstraint("carrier_code", "adapter_code", name="uq_carrier_query_config"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("carriers.carrier_code"),
        nullable=False,
    )
    adapter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    query_method: Mapped[CarrierQueryMethod] = mapped_column(
        Enum(CarrierQueryMethod, name="carrier_query_method", values_callable=enum_values),
        nullable=False,
    )
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=60, server_default="60")
    max_retry: Mapped[int] = mapped_column(nullable=False, default=3, server_default="3")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    remark: Mapped[Optional[str]] = mapped_column(Text)

    carrier: Mapped[Carrier] = relationship(back_populates="query_configs")


class CarrierQueryAdapter(Base, TimestampMixin):
    __tablename__ = "carrier_query_adapters"
    __table_args__ = (
        UniqueConstraint("adapter_code", name="uq_carrier_query_adapters_code"),
        CheckConstraint(
            "adapter_type in ('dedicated', 'general')",
            name="ck_carrier_query_adapters_type",
        ),
        Index("idx_carrier_query_adapters_type_order", "adapter_type", "display_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    adapter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CarrierAdapterType.DEDICATED.value,
        server_default=CarrierAdapterType.DEDICATED.value,
    )
    query_method: Mapped[CarrierQueryMethod] = mapped_column(
        Enum(CarrierQueryMethod, name="carrier_query_method", values_callable=enum_values),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    display_order: Mapped[int] = mapped_column(nullable=False, default=100, server_default="100")
    remark: Mapped[Optional[str]] = mapped_column(Text)


class CarrierAgent(Base, TimestampMixin):
    __tablename__ = "carrier_agents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(128))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(64))
    contact_emails: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    remark: Mapped[Optional[str]] = mapped_column(Text)
