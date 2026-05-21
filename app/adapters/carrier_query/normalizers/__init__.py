from app.adapters.carrier_query.normalizers.base import (
    CarrierResponseNormalizer,
    NormalizerRegistry,
    normalizer_registry,
)
from app.adapters.carrier_query.normalizers.cz import CZNormalizer
from app.adapters.carrier_query.normalizers.ek import EKNormalizer

normalizer_registry.register(CZNormalizer())
normalizer_registry.register(EKNormalizer())

__all__ = [
    "CarrierResponseNormalizer",
    "CZNormalizer",
    "EKNormalizer",
    "NormalizerRegistry",
    "normalizer_registry",
]
