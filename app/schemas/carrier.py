from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CarrierQueryMethod


class CarrierCreate(BaseModel):
    carrier_code: str = Field(max_length=16)
    carrier_name: str = Field(max_length=128)
    carrier_name_en: str | None = Field(default=None, max_length=128)
    enabled: bool = True


class CarrierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carrier_code: str
    carrier_name: str
    carrier_name_en: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CarrierPrefixMappingCreate(BaseModel):
    prefix: str = Field(max_length=8)
    carrier_code: str = Field(max_length=16)
    adapter_code: str = Field(max_length=64)
    query_method: CarrierQueryMethod = CarrierQueryMethod.HYBRID
    enabled: bool = True
    remark: str | None = None


class CarrierPrefixMappingUpdate(BaseModel):
    carrier_code: str | None = Field(default=None, max_length=16)
    adapter_code: str | None = Field(default=None, max_length=64)
    query_method: CarrierQueryMethod | None = None
    enabled: bool | None = None
    remark: str | None = None


class CarrierPrefixMappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prefix: str
    carrier_code: str
    adapter_code: str
    query_method: CarrierQueryMethod
    enabled: bool
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
