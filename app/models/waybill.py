from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlertLevel, CarrierQueryMethod, OfficialEventType, QueryStatus, WaybillLifecycleStatus, enum_values
from app.models.mixins import CreatedAtMixin, TimestampMixin


class WaybillBoard(Base, TimestampMixin):
    __tablename__ = "waybill_boards"
    __table_args__ = (
        Index("idx_waybill_boards_board_no", "board_no"),
        Index("idx_waybill_boards_consignee_contact_id", "consignee_contact_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    board_no: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    actual_board_no: Mapped[Optional[str]] = mapped_column(String(128))
    consignee_contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("consignee_contacts.id"))
    consignee_text: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    waybills: Mapped[list[AirWaybill]] = relationship(back_populates="board")

    @property
    def member_count(self) -> int:
        return len(self.waybills or [])

    @property
    def total_booked_volume(self) -> Decimal:
        return sum((item.booked_volume or Decimal("0.000") for item in self.waybills or []), Decimal("0.000"))


class AirWaybill(Base, TimestampMixin):
    __tablename__ = "air_waybills"
    __table_args__ = (
        Index("idx_air_waybills_waybill_no", "waybill_no"),
        Index("idx_air_waybills_carrier_code", "carrier_code"),
        Index("idx_air_waybills_lifecycle_status", "lifecycle_status"),
        Index("idx_air_waybills_next_query_at", "next_query_at"),
        Index("idx_air_waybills_created_at", "created_at"),
        Index("idx_air_waybills_route_staff_id", "route_staff_id"),
        Index("idx_air_waybills_carrier_agent_id", "carrier_agent_id"),
        Index("idx_air_waybills_consignee_contact_id", "consignee_contact_id"),
        Index("idx_air_waybills_board_id", "board_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    carrier_prefix: Mapped[Optional[str]] = mapped_column(String(8))
    carrier_code: Mapped[Optional[str]] = mapped_column(String(16), ForeignKey("carriers.carrier_code"))

    departure_port: Mapped[Optional[str]] = mapped_column(String(16))
    destination_port: Mapped[Optional[str]] = mapped_column(String(16))
    agent: Mapped[Optional[str]] = mapped_column(String(128))
    carrier_agent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("carrier_agents.id"))
    warehouse_no: Mapped[Optional[str]] = mapped_column(String(128))
    consignee: Mapped[Optional[str]] = mapped_column(String(255))
    consignee_contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("consignee_contacts.id"))
    board_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("waybill_boards.id", ondelete="SET NULL"))

    document_operator_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    route_staff_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    data_charge: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    document_cutoff_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    booked_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    booked_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    density: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))

    quotation: Mapped[Optional[str]] = mapped_column(String(64))
    include_tc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    warehouse_data_remark: Mapped[Optional[str]] = mapped_column(Text)
    notify_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    pickup_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    internal_remark: Mapped[Optional[str]] = mapped_column(Text)
    customer_remark: Mapped[Optional[str]] = mapped_column(Text)

    air_freight_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    other_charge: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    payment_date: Mapped[Optional[date]] = mapped_column(Date)

    lifecycle_status: Mapped[WaybillLifecycleStatus] = mapped_column(
        Enum(WaybillLifecycleStatus, name="waybill_lifecycle_status", values_callable=enum_values),
        nullable=False,
        default=WaybillLifecycleStatus.CREATED,
        server_default=WaybillLifecycleStatus.CREATED.value,
    )
    alert_level: Mapped[Optional[AlertLevel]] = mapped_column(
        Enum(AlertLevel, name="alert_level", values_callable=enum_values),
    )

    monitor_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    first_monitor_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_query_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_query_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    consecutive_query_failures: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    carrier_agent = relationship("CarrierAgent", lazy="joined")
    consignee_contact = relationship("ConsigneeContact", lazy="joined")
    board: Mapped[Optional[WaybillBoard]] = relationship(back_populates="waybills")
    plan: Mapped[Optional[WaybillPlan]] = relationship(back_populates="waybill", cascade="all, delete-orphan")
    official_info: Mapped[Optional[WaybillOfficialInfo]] = relationship(
        back_populates="waybill",
        cascade="all, delete-orphan",
    )
    official_flight_segments: Mapped[list[WaybillOfficialFlightSegment]] = relationship(
        back_populates="waybill",
        cascade="all, delete-orphan",
    )
    status_events: Mapped[list[WaybillStatusEvent]] = relationship(
        back_populates="waybill",
        cascade="all, delete-orphan",
    )
    assembly_events: Mapped[list[WaybillAssemblyEvent]] = relationship(
        back_populates="waybill",
        cascade="all, delete-orphan",
    )
    query_snapshots: Mapped[list[WaybillQuerySnapshot]] = relationship(
        back_populates="waybill",
        cascade="all, delete-orphan",
    )

    @property
    def official_estimated_flight_date(self) -> date | None:
        for segment in sorted(self.official_flight_segments, key=lambda item: item.segment_order):
            if segment.flight_date is not None:
                return segment.flight_date
        return None


class WaybillPlan(Base, TimestampMixin):
    __tablename__ = "waybill_plans"
    __table_args__ = (
        Index("idx_waybill_plans_flight_date", "planned_flight_date"),
        Index("idx_waybill_plans_flight_no", "planned_flight_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    planned_flight_no: Mapped[Optional[str]] = mapped_column(String(32))
    planned_flight_date: Mapped[Optional[date]] = mapped_column(Date)
    planned_destination: Mapped[Optional[str]] = mapped_column(String(16))
    planned_route_text: Mapped[Optional[str]] = mapped_column(String(255))

    waybill: Mapped[AirWaybill] = relationship(back_populates="plan")


class WaybillQuerySnapshot(Base):
    __tablename__ = "waybill_query_snapshots"
    __table_args__ = (
        Index("idx_query_snapshots_waybill_id", "waybill_id"),
        Index("idx_query_snapshots_status", "query_status"),
        Index("idx_query_snapshots_queried_at", "queried_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
    )
    carrier_code: Mapped[Optional[str]] = mapped_column(String(16))
    adapter_code: Mapped[Optional[str]] = mapped_column(String(64))
    query_method: Mapped[Optional[CarrierQueryMethod]] = mapped_column(
        Enum(CarrierQueryMethod, name="carrier_query_method", values_callable=enum_values),
    )
    query_status: Mapped[QueryStatus] = mapped_column(
        Enum(QueryStatus, name="query_status", values_callable=enum_values),
        nullable=False,
    )
    raw_response: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    queried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    waybill: Mapped[AirWaybill] = relationship(back_populates="query_snapshots")


class WaybillOfficialFlightSegment(Base, TimestampMixin):
    __tablename__ = "waybill_official_flight_segments"
    __table_args__ = (
        Index("idx_official_segments_waybill_id", "waybill_id"),
        Index("idx_official_segments_flight_no", "flight_no"),
        Index("idx_official_segments_flight_date", "flight_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
    )
    booking_no: Mapped[Optional[str]] = mapped_column(String(64))
    route_text: Mapped[Optional[str]] = mapped_column(String(255))
    segment_order: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    departure_airport: Mapped[Optional[str]] = mapped_column(String(16))
    arrival_airport: Mapped[Optional[str]] = mapped_column(String(16))
    flight_no: Mapped[Optional[str]] = mapped_column(String(32))
    flight_date: Mapped[Optional[date]] = mapped_column(Date)
    pieces: Mapped[Optional[int]] = mapped_column()
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    booking_type: Mapped[Optional[str]] = mapped_column(String(32))
    departure_planned_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    departure_actual_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    arrival_planned_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    arrival_actual_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    source_snapshot_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    waybill: Mapped[AirWaybill] = relationship(back_populates="official_flight_segments")


class WaybillOfficialInfo(Base, TimestampMixin):
    __tablename__ = "waybill_official_infos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    official_waybill_no: Mapped[Optional[str]] = mapped_column(String(64))
    carrier_text: Mapped[Optional[str]] = mapped_column(String(128))
    route_text: Mapped[Optional[str]] = mapped_column(String(255))
    goods_name: Mapped[Optional[str]] = mapped_column(Text)
    total_pieces: Mapped[Optional[int]] = mapped_column()
    total_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    total_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    source_snapshot_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    waybill: Mapped[AirWaybill] = relationship(back_populates="official_info")


class WaybillStatusEvent(Base, CreatedAtMixin):
    __tablename__ = "waybill_status_events"
    __table_args__ = (
        UniqueConstraint("waybill_id", "event_hash", name="uq_status_event_hash"),
        Index("idx_status_events_waybill_id", "waybill_id"),
        Index("idx_status_events_type", "normalized_event_type"),
        Index("idx_status_events_time", "event_time_local"),
        Index("idx_status_events_flight_no", "flight_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_time_local: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    event_time_text: Mapped[Optional[str]] = mapped_column(String(128))
    event_city: Mapped[Optional[str]] = mapped_column(String(128))
    airport_code: Mapped[Optional[str]] = mapped_column(String(16))
    flight_no: Mapped[Optional[str]] = mapped_column(String(32))
    status_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_event_type: Mapped[OfficialEventType] = mapped_column(
        Enum(OfficialEventType, name="official_event_type", values_callable=enum_values),
        nullable=False,
        default=OfficialEventType.UNKNOWN,
        server_default=OfficialEventType.UNKNOWN.value,
    )
    pieces: Mapped[Optional[int]] = mapped_column()
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    source_snapshot_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    event_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    waybill: Mapped[AirWaybill] = relationship(back_populates="status_events")


class WaybillAssemblyEvent(Base, CreatedAtMixin):
    __tablename__ = "waybill_assembly_events"
    __table_args__ = (UniqueConstraint("waybill_id", "event_hash", name="uq_assembly_event_hash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("air_waybills.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_time_local: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))
    event_time_text: Mapped[Optional[str]] = mapped_column(String(128))
    event_city: Mapped[Optional[str]] = mapped_column(String(128))
    status_text: Mapped[str] = mapped_column(Text, nullable=False)
    uld_no: Mapped[Optional[str]] = mapped_column(String(64))
    pieces: Mapped[Optional[int]] = mapped_column()
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    source_snapshot_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    event_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    waybill: Mapped[AirWaybill] = relationship(back_populates="assembly_events")
