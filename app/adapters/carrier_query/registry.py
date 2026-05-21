from app.adapters.carrier_query.base import CarrierQueryAdapter
from app.adapters.carrier_query.cz_adapter import CZAdapter
from app.adapters.carrier_query.ek_adapter import EKAdapter
from app.adapters.carrier_query.general_adapter import GeneralAdapter


GENERAL_ADAPTER_CODE = GeneralAdapter.adapter_code


class CarrierAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CarrierQueryAdapter] = {
            CZAdapter.adapter_code: CZAdapter(),
            EKAdapter.adapter_code: EKAdapter(),
            GeneralAdapter.adapter_code: GeneralAdapter(),
        }

    def get(self, adapter_code: str | None) -> CarrierQueryAdapter | None:
        if adapter_code is None:
            return None
        return self._adapters.get(adapter_code)

    def get_general(self) -> CarrierQueryAdapter | None:
        return self.get(GENERAL_ADAPTER_CODE)


registry = CarrierAdapterRegistry()
