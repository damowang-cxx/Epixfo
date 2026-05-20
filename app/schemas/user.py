from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRoleCode


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: UserRoleCode
    name: str
    description: str | None = None


class UserBase(BaseModel):
    username: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)


class UserCreate(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=6)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    role_codes: list[UserRoleCode]


class UserUpdate(UserBase):
    password: str | None = Field(default=None, min_length=6)
    role_codes: list[UserRoleCode] | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    last_seen_at: datetime | None = None
    roles: list[RoleOut] = []
    created_at: datetime
    updated_at: datetime
