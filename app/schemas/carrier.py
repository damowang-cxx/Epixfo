from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CarrierAdapterType, CarrierQueryMethod


class CarrierCreate(BaseModel):
    carrier_code: str = Field(max_length=16)
    carrier_name: str = Field(max_length=128)
    carrier_name_en: str | None = Field(default=None, max_length=128)
    enabled: bool = True


class CarrierUpdate(BaseModel):
    carrier_name: str | None = Field(default=None, max_length=128)
    carrier_name_en: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None


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


class CarrierQueryAdapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    adapter_code: str
    display_name: str
    adapter_type: CarrierAdapterType
    query_method: CarrierQueryMethod
    enabled: bool
    display_order: int
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class CarrierQueryAdapterOrderUpdate(BaseModel):
    adapter_codes: list[str] = Field(default_factory=list)


class CarrierAgentCreate(BaseModel):
    agent_name: str = Field(max_length=128)
    contact_person: str | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    contact_emails: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    remark: str | None = None


class CarrierAgentUpdate(BaseModel):
    agent_name: str | None = Field(default=None, max_length=128)
    contact_person: str | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    contact_emails: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    remark: str | None = None


class CarrierAgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    contact_person: str | None = None
    contact_phone: str | None = None
    contact_emails: str | None = None
    enabled: bool
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
