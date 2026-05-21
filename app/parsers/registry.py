from app.parsers.base import CarrierParser
from app.parsers.cz_parser import CZParser
from app.parsers.ek_parser import EKParser
from app.parsers.general_parser import GeneralParser


class CarrierParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, CarrierParser] = {
            "cz_adapter": CZParser(),
            "ek_adapter": EKParser(),
            "general_adapter": GeneralParser(),
        }

    def get(self, adapter_code: str | None) -> CarrierParser | None:
        if adapter_code is None:
            return None
        return self._parsers.get(adapter_code)


parser_registry = CarrierParserRegistry()
