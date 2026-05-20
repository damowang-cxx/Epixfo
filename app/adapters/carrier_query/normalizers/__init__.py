from app.adapters.carrier_query.normalizers.base import (
    CarrierResponseNormalizer,
    NormalizerRegistry,
    normalizer_registry,
)
from app.adapters.carrier_query.normalizers.cz import CZNormalizer

normalizer_registry.register(CZNormalizer())

__all__ = [
    "CarrierResponseNormalizer",
    "CZNormalizer",
    "NormalizerRegistry",
    "normalizer_registry",
]
