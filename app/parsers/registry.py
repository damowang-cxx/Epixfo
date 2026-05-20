from app.parsers.base import CarrierParser
from app.parsers.cz_parser import CZParser


class CarrierParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, CarrierParser] = {"cz_adapter": CZParser()}

    def get(self, adapter_code: str | None) -> CarrierParser | None:
        if adapter_code is None:
            return None
        return self._parsers.get(adapter_code)


parser_registry = CarrierParserRegistry()
