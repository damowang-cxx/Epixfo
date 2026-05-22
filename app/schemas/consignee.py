from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- Consignee（厂商）----

class ConsigneeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    remark: str | None = None


class ConsigneeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    remark: str | None = None


class ConsigneeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


# ---- ConsigneeContact（收件人记录）----

class ConsigneeContactCreate(BaseModel):
    consignee_id: int
    name: str = Field(min_length=1, max_length=128)
    address: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    tax_info: str | None = None
    notify_info: str | None = None
    remark: str | None = None
    enabled: bool = True


class ConsigneeContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    address: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    tax_info: str | None = None
    notify_info: str | None = None
    remark: str | None = None
    enabled: bool | None = None


class ConsigneeContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consignee_id: int
    name: str
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_info: str | None = None
    notify_info: str | None = None
    remark: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ConsigneeNotifyPartyUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    address: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    tax_info: str | None = None
    remark: str | None = None
    enabled: bool = True


class ConsigneeNotifyPartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consignee_contact_id: int
    name: str
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_info: str | None = None
    remark: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime
