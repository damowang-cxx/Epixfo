from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.adapters.carrier_query.registry import registry
from app.core.exceptions import bad_request
from app.models import Carrier, CarrierAgent, CarrierPrefixMapping, CarrierQueryAdapter
from app.models.enums import CarrierAdapterType, CarrierQueryMethod
from app.repositories.carrier_repository import CarrierRepository
from app.schemas.carrier import (
    CarrierAgentCreate,
    CarrierAgentUpdate,
    CarrierCreate,
    CarrierQueryAdapterOrderUpdate,
    CarrierUpdate,
    CarrierPrefixMappingCreate,
    CarrierPrefixMappingUpdate,
)
from app.utils.waybill_utils import carrier_prefix_from_waybill


DEFAULT_QUERY_ADAPTERS = {
    "cz_adapter": {
        "display_name": "南航 CZ 查询",
        "adapter_type": CarrierAdapterType.DEDICATED.value,
        "query_method": CarrierQueryMethod.HYBRID,
        "display_order": 10,
        "remark": "南航专属查询适配器",
    },
    "ek_adapter": {
        "display_name": "阿联酋航空 EK 查询",
        "adapter_type": CarrierAdapterType.DEDICATED.value,
        "query_method": CarrierQueryMethod.PROTOCOL,
        "display_order": 20,
        "remark": "阿联酋航空专属查询适配器",
    },
    "general_adapter": {
        "display_name": "51tracking 通用查询",
        "adapter_type": CarrierAdapterType.GENERAL.value,
        "query_method": CarrierQueryMethod.PROTOCOL,
        "display_order": 1,
        "remark": "通用航司查询适配器",
    },
}


class CarrierService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CarrierRepository(db)

    def identify_waybill(self, waybill_no: str) -> tuple[str, str, str | None]:
        prefix = carrier_prefix_from_waybill(waybill_no)
        mapping = self.repo.get_mapping_by_prefix(prefix)
        if mapping is None:
            return prefix, "UNKNOWN", None
        return prefix, mapping.carrier_code, mapping.adapter_code

    def list_carriers(self) -> list[Carrier]:
        return self.repo.list_carriers()

    def create_carrier(self, payload: CarrierCreate) -> Carrier:
        carrier = Carrier(**payload.model_dump())
        self.db.add(carrier)
        self.db.commit()
        self.db.refresh(carrier)
        return carrier

    def update_carrier(self, carrier_code: str, payload: CarrierUpdate) -> Carrier | None:
        carrier = self.repo.get_carrier(carrier_code)
        if carrier is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(carrier, key, value)
        self.db.commit()
        self.db.refresh(carrier)
        return carrier

    def list_mappings(self) -> list[CarrierPrefixMapping]:
        return self.repo.list_mappings()

    def create_mapping(self, payload: CarrierPrefixMappingCreate) -> CarrierPrefixMapping:
        self._ensure_query_adapter_known(payload.adapter_code)
        mapping = CarrierPrefixMapping(**payload.model_dump())
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def update_mapping(self, mapping_id: int, payload: CarrierPrefixMappingUpdate) -> CarrierPrefixMapping | None:
        mapping = self.repo.get_mapping(mapping_id)
        if mapping is None:
            return None
        if payload.adapter_code is not None:
            self._ensure_query_adapter_known(payload.adapter_code)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(mapping, key, value)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def list_query_adapters(self) -> list[CarrierQueryAdapter]:
        return self.repo.list_query_adapters()

    def list_general_query_adapters(self, enabled_only: bool = True) -> list[CarrierQueryAdapter]:
        return self.repo.list_general_query_adapters(enabled_only=enabled_only)

    def adapter_type_for_code(self, adapter_code: str | None) -> str | None:
        if not adapter_code:
            return None
        item = self.repo.get_query_adapter(adapter_code)
        if item is not None:
            return item.adapter_type
        default = DEFAULT_QUERY_ADAPTERS.get(adapter_code)
        if default is not None:
            return str(default["adapter_type"])
        if registry.get(adapter_code) is not None:
            return CarrierAdapterType.DEDICATED.value
        return None

    def _ensure_query_adapter_known(self, adapter_code: str) -> None:
        if self.repo.get_query_adapter(adapter_code) is not None:
            return
        if adapter_code in DEFAULT_QUERY_ADAPTERS and registry.get(adapter_code) is not None:
            return
        raise bad_request("carrier_query_adapter_not_found")

    def update_general_adapter_order(self, payload: CarrierQueryAdapterOrderUpdate) -> list[CarrierQueryAdapter]:
        general_adapters = self.repo.list_general_query_adapters(enabled_only=False)
        general_by_code = {item.adapter_code: item for item in general_adapters}
        requested_codes = []
        seen = set()
        for adapter_code in payload.adapter_codes:
            if adapter_code in seen:
                continue
            if adapter_code not in general_by_code:
                raise bad_request("general_adapter_not_found")
            requested_codes.append(adapter_code)
            seen.add(adapter_code)

        ordered_codes = requested_codes + [item.adapter_code for item in general_adapters if item.adapter_code not in seen]
        for index, adapter_code in enumerate(ordered_codes, start=1):
            general_by_code[adapter_code].display_order = index

        self.db.commit()
        return self.repo.list_general_query_adapters(enabled_only=False)

    def list_agents(self) -> list[CarrierAgent]:
        return self.repo.list_agents()

    def create_agent(self, payload: CarrierAgentCreate) -> CarrierAgent:
        agent = CarrierAgent(**payload.model_dump())
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update_agent(self, agent_id: int, payload: CarrierAgentUpdate) -> CarrierAgent | None:
        agent = self.repo.get_agent(agent_id)
        if agent is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(agent, key, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_agent(self, agent_id: int) -> CarrierAgent | None:
        return self.repo.get_agent(agent_id)
