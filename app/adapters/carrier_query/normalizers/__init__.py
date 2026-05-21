from app.adapters.carrier_query.normalizers.base import (
    CarrierResponseNormalizer,
    NormalizerRegistry,
    normalizer_registry,
)
from app.adapters.carrier_query.normalizers.cz import CZNormalizer
from app.adapters.carrier_query.normalizers.ek import EKNormalizer
from app.adapters.carrier_query.normalizers.general import GeneralNormalizer

normalizer_registry.register(CZNormalizer())
normalizer_registry.register(EKNormalizer())
normalizer_registry.register(GeneralNormalizer())

__all__ = [
    "CarrierResponseNormalizer",
    "CZNormalizer",
    "EKNormalizer",
    "GeneralNormalizer",
    "NormalizerRegistry",
    "normalizer_registry",
]
