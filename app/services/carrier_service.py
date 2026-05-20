from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.models import Carrier, CarrierPrefixMapping
from app.repositories.carrier_repository import CarrierRepository
from app.schemas.carrier import CarrierCreate, CarrierPrefixMappingCreate, CarrierPrefixMappingUpdate
from app.utils.waybill_utils import carrier_prefix_from_waybill


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

    def list_mappings(self) -> list[CarrierPrefixMapping]:
        return self.repo.list_mappings()

    def create_mapping(self, payload: CarrierPrefixMappingCreate) -> CarrierPrefixMapping:
        mapping = CarrierPrefixMapping(**payload.model_dump())
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def update_mapping(self, mapping_id: int, payload: CarrierPrefixMappingUpdate) -> CarrierPrefixMapping | None:
        mapping = self.repo.get_mapping(mapping_id)
        if mapping is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(mapping, key, value)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping
