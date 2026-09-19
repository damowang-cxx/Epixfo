from pydantic import BaseModel, ConfigDict, Field, field_validator


class DestinationPortCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str = Field(min_length=3, max_length=16, pattern=r"^[A-Z0-9]+$")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class ReceiptDestinationUpdate(BaseModel):
    # None restores automatic detection; an empty list explicitly clears ownership.
    destination_ports: list[str] | None = Field(max_length=1)
