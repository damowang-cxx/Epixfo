from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Carrier, CarrierAgent, CarrierPrefixMapping, CarrierQueryConfig


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

    def list_agents(self, carrier_code: str | None = None) -> list[CarrierAgent]:
        stmt = select(CarrierAgent).order_by(CarrierAgent.carrier_code, CarrierAgent.agent_name)
        if carrier_code:
            stmt = stmt.where(CarrierAgent.carrier_code == carrier_code)
        return list(self.db.scalars(stmt))

    def get_agent(self, agent_id: int) -> CarrierAgent | None:
        return self.db.get(CarrierAgent, agent_id)
