"""承运人响应清洗层。

每家航司 spider 直出的 dict 字段名差异很大；本层把它们翻译成 Parser
（[app/parsers](../../../parsers)）期待的"统一形态" dict：

    {
        "waybill_info":     {...},          # 单条
        "booking_info":     [{...}, ...],   # 航段 / 订舱信息
        "status_events":    [{...}, ...],   # 货物状态事件流
        "assembly_events":  [{...}, ...],   # 装载 / 拆板事件
        # ...额外原始字段以承运人小写代码为命名空间存留备份
    }

每家航司一个 normalizer 子类，通过 `adapter_code` 路由。
"""

from __future__ import annotations

from typing import Any, Protocol


class CarrierResponseNormalizer(Protocol):
    adapter_code: str

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        ...


class NormalizerRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CarrierResponseNormalizer] = {}

    def register(self, normalizer: CarrierResponseNormalizer) -> None:
        self._items[normalizer.adapter_code] = normalizer

    def get(self, adapter_code: str | None) -> CarrierResponseNormalizer | None:
        if not adapter_code:
            return None
        return self._items.get(adapter_code)


normalizer_registry = NormalizerRegistry()
