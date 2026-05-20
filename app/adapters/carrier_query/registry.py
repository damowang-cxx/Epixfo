from app.adapters.carrier_query.base import CarrierQueryAdapter
from app.adapters.carrier_query.cz_adapter import CZAdapter


class CarrierAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CarrierQueryAdapter] = {
            CZAdapter.adapter_code: CZAdapter(),
        }

    def get(self, adapter_code: str | None) -> CarrierQueryAdapter | None:
        if adapter_code is None:
            return None
        return self._adapters.get(adapter_code)


registry = CarrierAdapterRegistry()
