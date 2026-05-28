from pydantic import BaseModel, Field


class TableColumnPreferenceIn(BaseModel):
    column_order: list[str] = Field(default_factory=list, max_length=100)


class TableColumnPreferenceOut(BaseModel):
    table_key: str
    column_order: list[str]
