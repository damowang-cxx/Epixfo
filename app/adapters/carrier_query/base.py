from dataclasses import dataclass
from typing import Any, Protocol

from app.models.enums import CarrierQueryMethod, QueryStatus


@dataclass
class CarrierQueryResult:
    status: QueryStatus
    carrier_code: str
    adapter_code: str
    query_method: CarrierQueryMethod
    raw_response: dict[str, Any] | None = None
    raw_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class CarrierQueryAdapter(Protocol):
    adapter_code: str
    carrier_code: str
    query_method: CarrierQueryMethod

    async def query(self, waybill_no: str) -> CarrierQueryResult:
        ...
