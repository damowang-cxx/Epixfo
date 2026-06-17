from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Carrier, CarrierAgent, CarrierPrefixMapping, CarrierQueryAdapter, CarrierQueryConfig
from app.models.enums import CarrierAdapterType


class CarrierRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_carrier(self, carrier_code: str) -> Carrier | None:
        return self.db.scalar(select(Carrier).where(Carrier.carrier_code == carrier_code))

    def list_carriers(self) -> list[Carrier]:
        return list(self.db.scalars(select(Carrier).order_by(Carrier.carrier_code)))

    def get_mapping_by_prefix(self, prefix: str) -> CarrierPrefixMapping | None:
        return self.db.scalar(
            select(CarrierPrefixMapping).where(CarrierPrefixMapping.prefix == prefix, CarrierPrefixMapping.enabled.is_(True))
        )

    def list_mappings(self) -> list[CarrierPrefixMapping]:
        return list(self.db.scalars(select(CarrierPrefixMapping).order_by(CarrierPrefixMapping.prefix)))

    def get_mapping(self, mapping_id: int) -> CarrierPrefixMapping | None:
        return self.db.get(CarrierPrefixMapping, mapping_id)

    def get_query_config(self, carrier_code: str, adapter_code: str) -> CarrierQueryConfig | None:
        return self.db.scalar(
            select(CarrierQueryConfig).where(
                CarrierQueryConfig.carrier_code == carrier_code,
                CarrierQueryConfig.adapter_code == adapter_code,
                CarrierQueryConfig.enabled.is_(True),
            )
        )

    def get_query_adapter(self, adapter_code: str | None) -> CarrierQueryAdapter | None:
        if not adapter_code:
            return None
        return self.db.scalar(select(CarrierQueryAdapter).where(CarrierQueryAdapter.adapter_code == adapter_code))

    def list_query_adapters(self) -> list[CarrierQueryAdapter]:
        return list(
            self.db.scalars(
                select(CarrierQueryAdapter).order_by(
                    CarrierQueryAdapter.adapter_type,
                    CarrierQueryAdapter.display_order,
                    CarrierQueryAdapter.created_at,
                    CarrierQueryAdapter.adapter_code,
                )
            )
        )

    def list_general_query_adapters(self, enabled_only: bool = True) -> list[CarrierQueryAdapter]:
        stmt = select(CarrierQueryAdapter).where(CarrierQueryAdapter.adapter_type == CarrierAdapterType.GENERAL.value)
        if enabled_only:
            stmt = stmt.where(CarrierQueryAdapter.enabled.is_(True))
        return list(
            self.db.scalars(
                stmt.order_by(
                    CarrierQueryAdapter.display_order.asc(),
                    CarrierQueryAdapter.created_at.asc(),
                    CarrierQueryAdapter.adapter_code.asc(),
                )
            )
        )

    def list_agents(self) -> list[CarrierAgent]:
        return list(self.db.scalars(select(CarrierAgent).order_by(CarrierAgent.agent_name, CarrierAgent.id)))

    def get_agent(self, agent_id: int) -> CarrierAgent | None:
        return self.db.get(CarrierAgent, agent_id)
